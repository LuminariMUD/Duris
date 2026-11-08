# Race size: issues, gameplay impact, and recommended fixes

Reviewed 2026-11-08 against `b9bcce5e1c0081d373382c0e9cd3f18d48832b84` and the
current worktree. This is the issue companion to [race-size.md](race-size.md).
These are findings and recommendations; no gameplay changes have been made.
No deployed configuration, production state, or player data was inspected.

## Evidence and priorities

- **Reproduced:** exercised through extracted production functions or the actual
  snapshot/codec, with external services supplied by fixtures.
- **Verified contradiction:** conflicting conditions or representations are
  directly present in executable code. Intended behavior may still need a decision.
- **Design question:** the behavior could be intentional; do not automatically
  turn a surprising mechanic into a balance change.
- **Dormant:** the implementation is behind an unconditional return or otherwise
  unavailable through the current entry point.

Recommended priorities: **P1** for possible permanent identity loss; **P2** for
active mechanics/state inconsistencies; **P3** for lower-impact consistency,
configuration, and descriptions. These do not measure deployed encounter frequency.

`B` is stored size (`GET_SIZE`), `S` is effective size (`GET_ALT_SIZE`), and `T`
includes the applicable mounted bonus (`get_takedown_size`). Categories are
Tiny=1, Small=2, Medium=3, Large=4, Huge=5, Giant=6, Gargantuan=7.

**Correction to the original analysis:** corpseform immediately prints
“Temporarily disabled” and returns. Its implementation defects are dormant.
Draconic apotheosis is registered for Dragoon; Dragoon is disabled in ordinary
committed creation policy. That limits exposure but does not establish that no
existing or override-created Dragoon uses the spell.
[Corpseform guard](../../../src/classes/necromancy.c#L3230),
[apotheosis registration](../../../src/classes/skills.c#L5059),
[creation policy](../../../lib/creation_availability.cfg).

## F01 — Six conflicting racial size mappings

**Status:** verified contradiction. **Priority:** P2.

Player creation/login uses `set_char_size()`. The separate `race_size()` lookup
disagrees for six of the 37 PC race IDs. Training dummy profiles use that lookup;
NPC conversion uses it when stored size is `SIZE_DEFAULT`. Explicit authored NPC
size is separate. Tagged race changes also use the lookup, but corpseform's route
to such a state is currently disabled.

| Race | Creation/login B | race_size lookup | Recommended canonical PC size |
|---|---|---|---|
| Barbarian | Large (4) | Medium (3) | Large (4) |
| Death Knight | Large (4) | Medium (3) | Large (4) |
| Shadow Beast | Medium (3) | Large (4) | Medium (3) |
| Storm Giant | Huge (5) | Medium (3) | Huge (5) |
| Wight | Huge (5) | Medium (3) | Huge (5) |
| Harpy | Small (2) | Medium (3) | Small (2) |

These recommendations preserve current PC creation/login behavior. Changing PCs
to the lookup values would instead rebalance those races, especially Storm Giant
and Wight. That should be a separate, explicit decision.

### Barbarian

A real unmodified Barbarian is Large; its race-profile dummy is Medium. A Small
actor passes a generic ±1 size check against the dummy but fails against the
actual Barbarian. A Huge actor has the reverse result. Bash/headbutt/legsweep
comparisons can therefore misrepresent vulnerability and reach. The dormant
corpseform admission code also treats a Barbarian corpse as Medium.

**Fix:** canonical Large, shared by initialization and lookup. Preserve explicitly
authored mobile sizes.

### Death Knight

Large in the player path, Medium in the lookup. Small attackers appear able to
reach its profile but cannot reach the actual PC through a ±1 move; Huge attackers
appear unable to reach the profile but can reach the PC. It is a restricted race,
so exposure differs from normal-roster Barbarian.

**Fix:** canonical Large. Do not re-enable old transformation paths as part of
the consistency repair.

### Shadow Beast

Medium in the player path, Large in the lookup. A Small actor can reach the PC
through a ±1 check but not the dummy; a Huge actor can reach the dummy but not
the PC. Its racial enlarge innate then builds on different starting assumptions.

**Fix:** canonical Medium, matching current player initialization.

### Storm Giant

Huge in the player path, Medium in the lookup: a two-category difference. Medium
attackers pass ±1 checks against the profile but not the PC. Giant attackers are
adjacent to the actual PC but three categories from the profile. PC Storm Giant
is `RACE_SGIANT`, not NPC `RACE_GIANT`.

**Fix:** canonical Huge for PC Storm Giant. Leave NPC Giant's existing Giant
category separate.

### Wight

Huge in the player path, Medium in the lookup, producing the same two-category
reach error. Asymmetric capture, bodyslam, and grapple windows are also evaluated
against the wrong category in lookup-based representations. Wight is not Wraith.

**Fix:** canonical Huge for PC Wight; retain the distinct Wraith mapping.

### Harpy

Small in the player path, Medium in the lookup. A Large actor fails a generic
±1 check against the actual Harpy but passes against its profile. A Tiny actor
has the reverse result. Separate flutter/flight defenses do not fix this mismatch.

**Fix:** canonical Small; keep racial flight/evasion independent of category.

**Shared recommendation:** maintain one PC racial mapping used by initialization
and lookup. Add an exhaustive 37-PC-ID equivalence regression and representative
dummy/player comparisons. Check affected NPC defaults; do not overwrite explicit
mobile size fields.
[Player mapping](../../../src/account/nanny.c#L3827),
[lookup](../../../src/core/common.c#L184),
[dummy](../../../src/combat/training_dummy.c#L237),
[default NPC size](../../../src/mob/mobconv.c#L111),
[effective size](../../../src/core/utility.c#L5100).

## F02 — Temporary race can be saved without its restoration state

**Status:** reproduced snapshot/codec defect; live logout/relogin not exercised.
**Priority:** P1 for the registered dragon-form route; dormant for corpseform.

Snapshot capture writes current `GET_RACE(ch)` directly and separately drops
affects marked `AFFTYPE_NOSAVE`. Apotheosis changes race to Dragon and stores
the original race in an affect with that flag. A checkpoint can therefore retain
the temporary race while losing its restoration record. Reload materialization
assigns the saved race directly.

A probe linked to production snapshot capture and codec confirmed:

- Original Human, stored Medium, currently Dragon: decoded checkpoint contains
  Dragon race and Medium size, without the apotheosis restoration affect.
- A constructed corpseform state with original Barbarian, stored Large,
  currently Gnome: decoded checkpoint contains Gnome race and Large size,
  without the original-race tag. This demonstrates storage behavior, not access
  to the disabled corpseform spell.

**Impact:** save/reload can strand a transformed character in the temporary race,
changing racial checks, innates, equipment eligibility, and size assignment.
The checkpoint no longer contains the original race in these cases. No claim
is made that a particular live character has already suffered this.

**Fix:** choose a complete persistence contract. If the form should disappear
on leaving the game, capture permanent identity and omit dependent temporary
state without mutating the live character. If it should survive reload, persist
the complete reversible form and restoration record together. Merely changing
capture to `get_real_race()` is insufficient: that helper handles the race-change
tag but has its apotheosis fallback commented out.

**Verification needed:** capture/codec/materialize/login/expiry journeys for
save, quit, and crash recovery, checking race, stored/effective size, affects,
and innate/equipment restoration.
[Saved race](../../../src/player/player_snapshot_capture.c#L138),
[NOSAVE filter](../../../src/player/player_snapshot_capture.c#L310),
[capture caller](../../../src/player/player_save_pipeline.c#L310),
[transformation](../../../src/magic/magic.c#L30340),
[reload](../../../src/player/player_load_materialize.c#L227),
[real-race helper](../../../src/core/utility.c#L2102).

## F03 — Trip has an impossible body-size window

**Status:** verified contradiction. **Priority:** P2.

Horse-body, spider-body, and quadruped targets first require
`actor T >= target T+1`. A later check requires `target T >= actor T`.
No size pair satisfies both. An actor big enough for the first check fails
the later “too small” check; all others fail the first.

**Impact:** these bodies are effectively immune to successful trip at every
size. Growth cannot solve it. Failure sits the actor; some paths stop singing.

**Fix:** make the body rule explicit. My preference is to honor the early
“actor must be bigger” condition and allow exactly one-category-bigger actors
against these bodies, retaining the ordinary equal/one-bigger-target window
elsewhere. This changes current effective immunity and needs acceptance as a
gameplay rule. If immunity is intended, express it directly with accurate
feedback. Test all 49 size pairs for each body category.
[Body gate](../../../src/cmd/actoff.c#L12390),
[later gate](../../../src/cmd/actoff.c#L12438).

## F04 — NPC springleap eligibility contradicts the command

**Status:** verified contradiction with active AI callers. **Priority:** P2.

`isSpringable()` accepts ordinary targets one category smaller; the command
rejects all smaller targets. The helper rejects equal horse/spider-body targets;
the command permits exactly equal size for those bodies. The helper also rejects
all actors at ground elevation (`z_cord==0`), unlike command admission through
posture and footing.

**Impact:** NPCs select invalid leaps and pay posture/lag costs, skip legal leaps,
and skip helper-controlled leaping at ordinary ground elevation. Callers kneel
the NPC before invoking the command, so a false positive changes its state.

**Fix:** align helper size/body/ground conditions with command preconditions,
preserving the deliberate kneel step. Reuse one readable eligibility rule where
practical. Test ground NPC selection, ordinary size pairs, and equal horse/spider
targets.
[Helper](../../../src/cmd/actoff.c#L13892),
[command](../../../src/cmd/actoff.c#L11856),
[AI caller](../../../src/mob/mobact.c#L5858).

## F05 — Bash helper omits spider-body rejection

**Status:** verified contradiction. **Priority:** P2.

`isBashable()` requires horse-body targets to be strictly smaller but omits
spider body. Execution applies the restriction to both. Same-sized Driders can
pass the helper and then make the basher fall when the command runs.

**Impact:** NPCs waste an action, sit, and request two seconds of lag against a
target execution cannot bash. Other callers inherit misleading eligibility.

**Fix:** match actual command body restrictions in the helper. Test parity
across PC body types while preserving the accepted player bash window.
[Helper](../../../src/cmd/actoff.c#L8307),
[execution](../../../src/cmd/actoff.c#L8623),
[AI use](../../../src/mob/mobact.c#L6900).

## F06 — NPC gaze selection inherits unrelated bash restrictions

**Status:** verified mismatch. **Priority:** P2/P3 depending on intended AI reach.

`GOOD_FOR_GAZING()` first calls `isBashable()`. It therefore rejects targets two
categories smaller even though gaze permits them, and imports bash's body rules.
Its later −2 check cannot restore candidates already rejected by bash eligibility.

**Impact:** a Large gaze-using NPC can skip a legal gaze against a Small PC,
or skip a legal target because of bash-specific body restrictions.

**Fix:** use gaze's command conditions for gaze eligibility. Keep deliberate
AI preferences separate from hard admission. Test the −2 boundary and body cases.
[AI gate](../../../src/mob/mobact.c#L5505),
[gaze window](../../../src/cmd/actoff.c#L13224).

## F07 — Bash/tackle test the actor's quadruped race in a target-body condition

**Status:** verified operand inconsistency; intended rule uncertain.
**Priority:** P2 if correcting the likely wrong subject.

The condition combines the target's horse/spider traits with
`GET_RACE(actor)==RACE_QUADRUPED`, rather than the target's quadruped race.

**Impact:** quadruped NPC actors receive a special restriction against same-sized
or larger targets regardless of target body. Quadruped targets do not gain this
protection solely by being quadrupeds. Trip instead checks the target. Ordinary
animal shapechange uses disguise fields, so not every shapechanged PC reaches
this exact actor-race branch.

**Fix:** if this is body protection, change the subject to target and align the
helper. If quadrupeds need an attacking restriction, express that separately
with actor-specific feedback. I recommend the target-body interpretation, but
the current code alone does not prove historical intent.
[Bash](../../../src/cmd/actoff.c#L8624),
[tackle](../../../src/cmd/actoff.c#L9254),
[trip comparison](../../../src/cmd/actoff.c#L12391).

## F08 — Opposite flags cancel category but enlarge wins physical dimensions

**Status:** reproduced representation inconsistency. **Priority:** P2.

Effective size adds one for enlarge and subtracts one for reduce. Height/weight
instead choose enlarge first. Both flags can coexist, for example from innate
enlarge and reduction equipment.

**Impact:** normal effective category can coexist with 1.5× stored height and
2× body mass. Groundslam, living-character dragging, tracks, and corpse mass then
use enlarged physical values while reach/crowding use unchanged size.

**Fix:** define a consistent effective geometric state. My preference is to
cancel opposite flags for category, height, and weight. Preserve underlying
equipment sources; spell attribute-package cancellation needs its own explicit
rule. Test all four flag combinations and equipment-sourced flags.
[Category](../../../src/core/utility.c#L5100),
[physical precedence](../../../src/core/utils.h#L503),
[innate enlarge](../../../src/classes/innates.c#L2813).

## F09 — Cancellation clears a cached flag without consistently removing its source

**Status:** reproduced for infuriate enlargement. **Priority:** P2.

Reduce clears the cached enlarge bit and removes only `SPELL_ENLARGE` affects.
Infuriate uses `SKILL_INFURIATE`, so its enlarge source survives. Equipment
sources likewise do not disappear because the character's cached bit was cleared.
The reverse operation has the same source-versus-bit distinction.

**Impact:** a spell reports return to normal size, but surviving sources can
restore growth during affect recomputation. Associated stat effects can survive
the apparent cancellation. Timing depends on recalculation rather than the
stated action.

**Fix:** operate on the real source and rebuild derived flags. Decide whether
infuriate is cancellable and whether equipment growth can be suppressed. Report
uncancellable sources accurately. Test cancellation followed by recomputation.
[Cancellation](../../../src/magic/magic.c#L23268),
[infuriate source](../../../src/cmd/actoth.c#L995),
[affect aggregation](../../../src/magic/affects.c#L1717).

## F10 — Innate enlarge makes a later spell skip its stat package

**Status:** reproduced through the actual spell function. **Priority:** P2.

Innate enlarge creates a `SPELL_ENLARGE` affect with a size bit and no spell
stat modifiers. The ordinary spell sees that type and only refreshes records,
without installing missing STR/CON/AGI/DEX effects.

**Impact:** a Duergar using innate enlarge can receive the spell without its
normal attribute package. In the reproduced case the spell also shortens the
innate's five-hour duration to three hours. Application order changes the buff.
The reduce implementation has the analogous record-type collision, although
no ordinary racial reduce grant was found.

**Fix:** have spell application establish the full package without duplicating
existing modifiers. Distinguish size-only innate records or explicitly upgrade
an incomplete package. Decide duration refresh policy; test both application orders.
[Innate record](../../../src/classes/innates.c#L2832),
[spell apply/refresh split](../../../src/magic/magic.c#L23145),
[Duergar grant](../../../src/classes/innates.c#L579).

## F11 — Physical interactions ignore current effective size

**Status:** verified behavior; policy decisions needed. **Priority:** P2/P3.

These use stored `B`, so normal size flags do not move their category threshold:

- **Sneaky strike:** Small enlarged to Medium still cannot prepare against Large,
  despite being within one effective category.
- **Mount fit:** growth does not make the rider fail stored-size admission;
  reduction does not help an oversized rider pass it.
- **Wall of Air:** Large reduced to Medium keeps the Large 50% base passage
  chance instead of Medium's 25%, before stat adjustments.
- **Shout:** growth/reduction does not change racial base radius.
- **Improved listen:** distant-emote anonymity ignores current size changes.
- **Xorn/Golem/Djinni:** effective growth does not remove stored-size weaknesses
  or move the stored Giant/Gargantuan thresholds.
- **Giantbane:** Huge enlarged to effective Giant does not meet its exact
  stored-Giant trigger.
- **Physical disguise:** actor effective size is compared with copied target
  stored size; illusion mask instead compares effective size on both sides.

**Fix:** prefer effective `S` for current physical reach, fit, and displacement;
use mounted `T` where rider elevation/reach is intended. Review communication,
disguise, and Giantbane separately. Giantbane needs a choice between racial
identity and physical size. Do not mechanically replace every `GET_SIZE` call.
Each accepted rule needs a size-change regression.

This is a family of possible consistency bugs, not proof every stored-size use
is wrong. Attribute changes can still affect some paths indirectly.
[Sneaky strike](../../../src/cmd/actoff.c#L7281),
[mount](../../../src/classes/mount.c#L250),
[Wall of Air](../../../src/specs/specs.object.c#L6672),
[shout](../../../src/cmd/actcomm.c#L2032),
[listen](../../../src/net/listen.c#L307),
[pet procs](../../../src/specs/specs.mobile.c#L13215),
[Giantbane](../../../src/specs/specs.jot.c#L323),
[disguise](../../../src/classes/disguise.c#L303).

## F12 — Rider growth changes body mass but not mount burden

**Status:** verified inconsistency between physical readers. **Priority:** P2/P3.

`total_carried_weight(mount)` adds `rider->player.weight`; groundslam, dragging,
and tracks use `GET_WEIGHT(rider)`. Enlarge doubles only the latter.

**Impact:** a 150 lb rider enlarged to 300 lb burdens the mount as 150 lb plus
gear, while becoming harder to drag and dealing more mass-based groundslam
damage. Reduction does not lighten that mount-load calculation either.

**Fix:** use effective body mass for rider burden if growth changes actual
carried mass. Test encumbrance/movement immediately after flag changes, including
equipment changes. Keep carry capacity's STR dependence separate.
[Rider burden](../../../src/core/utility.c#L4343),
[effective mass](../../../src/core/utils.h#L508).

## F13 — PvP crowding omits the candidate's size from its budget

**Status:** verified algorithm; likely policy/consistency defect, intent unproven.
**Priority:** P2 if the budget should represent all attackers.

The check sums only other PCs already fighting the victim, excludes the actor,
and allows equality. A Small target has budget 32. One existing Huge attacker
costs 32, so a second Huge attacker is admitted despite combined cost 64.

**Impact:** this is not a total physical-capacity cap. Arrival order can affect
engagement: a Gargantuan arriving first blocks a later Small attacker; in reverse
order the Gargantuan is admitted and the Small participant can later fail its
own hit checks. Growth can suppress an existing participant's attacks.

**Fix:** decide whether the budget intentionally means “other attackers.” My
preference is projected total including the candidate, preserving the four-PC
limit and explicitly allowing at least one opponent so Tiny cannot become immune
to a single large melee attacker. Test arrival permutations, ongoing hits, and
mid-combat growth before changing this sensitive PvP rule.
[Budget](../../../src/combat/fight.c#L4171),
[hit gate](../../../src/combat/fight.c#L7943),
[engagement gate](../../../src/combat/fight.c#L8889).

## F14 — Buff-assisted shape learning outlasts the size buff

**Status:** verified behavior with an explicitly disabled reuse check; potential
balance issue, not proven accidental. **Priority:** design decision.

Learning requires equal effective size. Using a learned shape does not repeat
the check. A buff can qualify learning, expire, and leave the shape usable.
Using the form does not assign the creature's numeric size.

**Impact:** temporary growth can broaden lasting form access, and appearance/
shape innates can diverge from current numeric size. The code comment explicitly
points to learning-stage validation, so this may be intentional.

**Fix:** keep learning-only compatibility unless continuous compatibility is
desired. If changing it, validate use and define what happens when a buff expires
mid-form. Do not silently revoke learned forms during a generic size cleanup.
[Learning](../../../src/cmd/actnew.c#L2647),
[reuse check](../../../src/cmd/actnew.c#L2819),
[shape innates](../../../src/classes/innates.c#L380).

## F15 — Growth after grapple admission does not establish automatic release

**Status:** potential balance issue; no automatic-release exploit reproduced.
**Priority:** design decision.

Bearhug/headlock/leglock size limits are admission checks. The audit found no
general effective-size rule releasing an existing hold when either party grows.

**Impact:** eligibility to grab and eligibility to keep holding can diverge after
growth/reduction, depending on the hold's continuation and escape behavior.

**Fix:** decide whether limits apply only to initiation or throughout the hold.
For continuous limits, revalidate at existing transitions/maintenance points and
release linked affects cleanly. Avoid a new global polling system. Test both
participants' state and links on release.
[Bearhug](../../../src/combat/grapple.c#L354),
[headlock](../../../src/combat/grapple.c#L623),
[leglock](../../../src/combat/grapple.c#L1163).

## F16 — Dragon, elemental, and titan forms use different meanings of growth

**Status:** verified behavior; intended balance uncertain. **Priority:** design decision.

- Apotheosis changes race to Dragon but normally uses old stored size plus one
  enlarge step, rather than Dragon's Gargantuan lookup.
- Elemental form's growth wording does not itself add a category.
- Titan form adds two categories without multiplying body mass or height.

**Impact:** dragon-looking PCs may have much less reach than NPC Dragons. Titan
changes control windows without enlarge's mass-based damage/rescue consequences.

**Fix:** resolve F02 first. Preserve current numbers until the form contract is
accepted; automatically making dragon-form PCs Gargantuan would substantially
rebalance combat and crowding. Document category, mass, and wording per form.
[Apotheosis](../../../src/magic/magic.c#L30340),
[elemental form](../../../src/magic/magic.c#L17172),
[effective size](../../../src/core/utility.c#L5100),
[mass/height](../../../src/core/utils.h#L503).

## F17 — Tiny-base reduction refuses before cancelling enlarge

**Status:** reproduced edge case. **Priority:** P3; ordinary PC bases are ≥Small.

The reduce spell's stored-Tiny guard precedes opposite-effect cancellation.
A base-Tiny creature enlarged to Small is refused instead of returned to Tiny.
None of the 37 PC base assignments is Tiny; this mainly affects NPC/form/staff states.

**Impact:** otherwise symmetric cancellation fails at this boundary. Stored-size
guards also do not express current effective bounds under tags/multiple flags.

**Fix:** process applicable cancellation before rejecting reduction below the
minimum, then validate the resulting state. Test Tiny+enlarge and the maximum
boundary with different growth sources.
[Early guard](../../../src/magic/magic.c#L23258),
[later cancellation](../../../src/magic/magic.c#L23268).

## F18 — Small-target Golem throws precede the combat gate

**Status:** verified call ordering and legacy delivery; exploit not reproduced.
**Priority:** P2 investigation.

The Golem's stored-size ≤Small branch runs before `CanDoFightMove()`. Throwing
uses direct room removal/insertion. A blocked throw subtracts 1–30 HP directly
and calls `update_pos()`.

**Impact:** Small targets can be moved/damaged before the combat gate. Direct
movement bypasses the forced-movement policy used by newer kick/tackle paths;
direct HP subtraction bypasses normal damage delivery/attribution. Practical
protected-target and lethal cases still require executable journeys.

**Fix:** check combat eligibility before effects and use existing `move_forced`
and damage entry points. Test safe rooms, private destinations, anchored targets,
blocked exits, lethal damage, and combat cleanup. Reuse existing infrastructure.
[Golem branch](../../../src/specs/specs.mobile.c#L13314),
[later gate](../../../src/specs/specs.mobile.c#L13360),
[existing forced movement](../../../src/cmd/actoff.c#L4539).

## F19 — Snow Ogre collision attributes damage to the second PC

**Status:** verified argument direction; kill-credit effect unverified.
**Priority:** P2 investigation.

The NPC toss calls `damage(second PC, first PC, GET_WEIGHT(second PC)/2,
TYPE_UNDEFINED)`. The first PC takes damage; the second PC is passed as attacker.

**Impact:** an NPC-caused collision may be attributed to an uninvolved PC.
Lethal damage could affect kill/death credit or other combat side effects; exact
reward/attribution consequences require a collision journey. Mass formula and
responsibility for causing the collision are separate concerns.

**Fix:** keep the accepted mass formula if desired, but attribute the NPC-caused
damage to the responsible NPC through the appropriate damage path. Test lethal
and nonlethal collisions, including cleanup, before calling it resolved.
[Collision](../../../src/specs/specs.snogres.c#L341).

## F20 — Fallback configuration describes a different balance

**Status:** verified drift, not proof of wrong deployed tuning. **Priority:** P3.

| Setting | Committed value | Code fallback |
|---|---|---|
| Headbutt damage vs smaller | 1.15 | 1.10 |
| Headbutt damage vs larger | 1.00 | 0.90 |
| Bearhug NPC size reach | ±1 | ±3 |
| Headlock PC downward size reach | 1 | 2 |
| Leglock PC downward size reach | 1 | 2 |
| Groundslam upward size reach | 0 | 2 |
| Shieldpunch actor lag | 2 rounds | 1 round |

**Impact:** missing keys/incomplete configuration can change damage, reach,
and costs. Tests using fallback fixtures can pass while describing different
mechanics from committed tuning. Neither value is wrong merely by differing.

**Fix:** agree intended defaults, align fallbacks as appropriate, and test with
the committed/effective property set. Do not overwrite valid live tuning simply
to match a fallback.
[Properties](../../../lib/duris.properties#L2117),
[headbutt defaults](../../../src/cmd/actoff.c#L6284),
[grapple defaults](../../../src/combat/grapple.c#L354).

## F21 — Dormant corpseform overwrites its innate-mode marker

**Status:** verified dormant-code contradiction. **Priority:** fix before re-enabling.

`afrc` and `afcf` share one local `affected_type`. After selecting
`CORPSEFORM_INNATE=0` or `CORPSEFORM_REG=1`, assignment of original race through
`afrc->modifier` overwrites that mode before capturing the corpseform affect.

**Impact if re-enabled:** ordinary/superior innate behavior depends on original
race ID 1 (Human) versus other IDs, rather than the random superior-form result.
Non-Humans can get the form's innate behavior on the ordinary branch. F02's
persistence loss is an additional, independent re-enabling blocker.

**Fix:** use separate local records for mode and original race, then repair
persistence/expiry. Test both random outcomes from Human and non-Human races.
Keep the spell disabled until these paths work; the guard is not a bug to remove.
[Shared record/overwrite](../../../src/classes/necromancy.c#L3328),
[mode constants](../../../src/classes/necromancy.h#L54),
[innate consumer](../../../src/classes/innates.c#L394).

## F22 — Old physical initialization and descriptions are stale

**Status:** dormant calculation defect and description drift. **Priority:** P3.

Old `init_height_weight()` scales existing female height using integer
`number(90,100)/100`, then overwrites it with a different local height. Its female
height adjustment is ineffective. Its call in `do_reinitphys()` is after an
unconditional return, not ordinary creation's generator.

Current generator comments claim CON affects the result, but it never reads
CON. Growth messages say twice/half size while height changes by 1.5 or 1/1.5.
Wither's “decrease in size” branch changes hitroll/damroll/AC, not numeric size.

**Impact:** old physical initialization would be wrong if restored; descriptions
can mislead balance work, help writing, and testing. They do not prove missing
CON-to-size scaling or justify adding a size effect to Wither.

**Fix:** retire unused physical initialization when safe, or repair it only
when intentionally restoring that route. Correct descriptions to match current
mechanics. Avoid incidental CON scaling or Wither balance changes.
[Old generator](../../../src/account/nanny.c#L301),
[unreachable call](../../../src/cmd/actwiz.c#L6505),
[current generator](../../../src/account/nanny.c#L3668),
[physical macros](../../../src/core/utils.h#L503),
[Wither](../../../src/magic/magic.c#L2405).

## Behaviors to preserve unless explicitly rebalanced

- **Weapon handling follows base size for PCs.** The explicit
  [2026-11-08 follow-up](race-misc.md#2-huge-player-races-two-handed-weapons-in-one-hand)
  extends the discount to every Huge player race, adding Wight. Effective growth
  still does not grant it; NPCs retain their racial giant list.
- **Dwarf giant avoidance has an explicit target list.** Troll, Ogre, and NPC
  Giant qualify; the full `IS_GIANT` roster does not. Current facts text names
  these targets. Expand it only if the innate should cover all giant identities.
- **Different moves may have different size windows.** Capture, roundkick,
  gaze, and shieldpunch need not all use ±1. Repair contradictions while preserving
  accepted asymmetric rules.
- **NPC preferences may be conservative.** Branch/webwrap's `PT_SMALLER` selection
  is narrower than ability admission. This is an AI improvement candidate rather
  than proof the ability is broken.
- **Physical dimensions and category are distinct.** A Medium dwarf can be
  shorter than another Medium race without a bug. Do not derive all combat
  rules from inches or rewrite racial stats just to unify representations.

[Weapon hand cost](../../../src/cmd/actobj.c#L104),
[giant avoidance](../../../src/combat/fight.c#L9326),
[AI preferences](../../../src/mob/mobact.c#L6415).

## Recommended implementation order

1. Fix F02's permanent-identity checkpoint contract and prove recovery/expiry.
2. Unify F01's six mappings, preserving current PC sizes; check all 37 races,
   dummy profiles, and NPC defaults.
3. Resolve F03's intended trip body rule and repair F04–F07 command/AI parity.
4. Repair F08–F10 growth composition, source cancellation, and application order,
   including equipment-supplied flags.
5. Investigate F18/F19's movement/damage policy and attribution.
6. Decide F11–F17's physical-size, PvP, form, and hold policies individually;
   implement only accepted changes with applicable gameplay journeys.
7. Align agreed defaults/descriptions (F20/F22). Treat F21 and corpseform's F02
   case as prerequisites for any future re-enabling.

Avoid a wholesale size-system rewrite. A canonical PC mapping, consistent effect
state, and matching command/AI eligibility address the strongest findings without
introducing another configuration layer or rebalancing every class.

## Verification record and limits

- Current owning source and availability guards were reread for these findings.
- The earlier extracted-code audit covered all 37 PC assignments, 4,144 effective
  size combinations, 49 mount-size pairs, and crowding examples. Gameplay source
  remains at the reviewed baseline.
- A new probe linked production snapshot capture and codec. F02's temporary race
  survived the wire round-trip while its original-race affect did not. The
  corpseform state was constructed because that spell is disabled.
- A new probe extracted actual enlarge/reduce spell functions. It reproduced
  F09's surviving infuriate source, F10's missing stat package and 5→3 duration
  change, and F17's Tiny-base refusal. External services were fixtures.
- Earlier headbutt, Freedom of Movement, race-browser, and all-races-toggle tests
  passed; those passes do not mean these findings are fixed.

No live logout/relogin, deployed tuning audit, player repair, migration, or
deployment was performed. No C/C++ gameplay source changed and no GitHub issues
were filed. Scratch probes are under ignored `bin/tests/race-size-review/` and
are not a committed regression suite. Implemented fixes should add focused
permanent regressions and the applicable booted gameplay/persistence journeys.
