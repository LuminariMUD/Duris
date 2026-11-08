# Race innates: potential bugs, gameplay impact, and recommended fixes

Reviewed 2026-11-08 against checkout
`f08ca648c21bf73e544ae07b331026fe69e77fa8` and the supplied, locally untracked
[race-innates.md](race-innates.md). The reference describes the older
`b96dcdebbc9eb85a876c6bc64918b7a678d483d9` snapshot. Several fixes landed between
those snapshots, including during this review; resolved findings are recorded
separately below. This report changes no gameplay code or settings.

There are **27 open findings/review items**, not 27 proven unintended bugs.
They include executable contradictions, conditional defects, presentation
problems, and explicit balance decisions. Findings already covered by the
[stat](race-stats-issues.md) or [size](race-size-issues.md) reviews are linked
rather than treated as independent discoveries. Ordinary and restricted PC
races are both included; a restricted race does not imply an unreachable path.

## Evidence, priorities, and recommended order

**Source verified** means the cited implementation contains the behavior; it
does not mean a live encounter was reproduced. **Conditional** means the issue
requires a particular shape, equipment/prototype, or state. **Design decision**
means the behavior is established but its intent is not. **Presentation** and
**dormant** findings do not establish a current combat defect.

**P1:** prioritize a protected-room/hostile-action bypass. **P2:** active combat,
state, lifecycle, or resource inconsistency. **P3:** descriptions, conditional
content contracts, and balance decisions. These priorities do not measure live
frequency or imply that production runs this revision.

Recommended order:

1. Fix hostile admission for Blast/Faerie Fire (F01).
2. Fix Faerie Fire reveal, Troll-burn expiry, Eyeless's subject, Blast's save
   sign, and Shade Movement's lifetime (F02–F06).
3. Remove Doorkick's temporary travel; repair harmful defensive bonuses,
   rejected-use costs, cooldown displays, and totem string ownership
   (F07–F11/F16).
4. Reconcile body/size and buff-overlap contracts (F12–F15/F18) with the
   companion reviews. Decide the remaining design questions before changing
   racial balance. Do not restore removed innates merely to match old help.

## F01 — Blast and Faerie Fire bypass hostile-action admission

**Status:** source verified. **Priority:** P1. **Recommendation:** fix.

Original Illithid's Blast and Drow's Faerie Fire use `parse_victim()` and call
their spell functions directly. The parser selects a visible target or the
current opponent; it performs no combat admission. Neither wrapper nor its
called spell performs the common safe-room/peace/target-permission check.
The generic innate dispatcher verifies ownership and dispatches; its standing
posture requirement is not a hostile-action check.

**Gameplay:** a valid target can receive paralysis or an AC/concealment debuff
where an ordinary attack would be refused, including a safe room. Blast's
chance, freedom-of-movement, trusted-target and immunity checks still apply;
this is not guaranteed paralysis. Faerie Fire also lacks Blast's trusted-target
guard. No live protected-room encounter was run.

**Fix:** apply the existing hostile-action admission appropriate to each power
before consuming a use or applying effects. Preserve intentional ranged/mental
targeting rules rather than importing every melee-only restriction blindly.
Make an explicit choice about guard interception, then check any redirected
target. Keep successful spell defenses separate from admission.

**Verify:** safe room/zone, peace, self/master/protected targets, legal PvE/PvP,
current-opponent fallback, guards, and no effect or charge on refusal.
[Parser and wrappers](../../../src/classes/innates.c#L1056),
[Blast wrapper](../../../src/classes/innates.c#L2626),
[Faerie Fire wrapper](../../../src/classes/innates.c#L2661),
[Blast spell](../../../src/classes/psionics.c#L4035),
[Faerie Fire spell](../../../src/magic/magic.c#L18812),
[common admission](../../../src/classes/new_skills.c#L229).

## F02 — Faerie Fire can leave the outlined victim concealed

**Status:** source verified, two defects in one reveal path. **Priority:** P2.
**Recommendation:** fix both together.

The concealment-removal loop tests `affected_by_spell(ch, SPELL_CONCEALMENT)`
on the **caster**, then removes affects from the **victim**. With an unconcealed
caster, the victim's source affect remains. Separately, when the target was
invisible/concealed, the spell clears the bits and then sets
`AFF2_CONCEALMENT` again. Ordinary character visibility treats that bit as
concealment requiring detection, not as a publicly visible outline.

**Gameplay:** the Drow can land the AC penalty and announce purple flames while
ordinary observers still cannot see the victim. A surviving concealment affect
can also restore its state during recalculation. The caster's own concealment
incorrectly changes whether the victim's affect is removed.

**Fix:** inspect/remove the victim's concealment source, and represent an outline
without reusing a bit that hides its owner. Define which invisibility sources
Faerie Fire suppresses for its duration; removing only a cached bit is not
durable suppression. Preserve explicit exceptions for other concealment systems.

**Verify:** caster concealed/not concealed crossed with target invisibility,
concealment, disguise and detection; inspect third-party visibility immediately,
after equipment recalculation, and after expiry.
[Spell](../../../src/magic/magic.c#L18812),
[visibility rejection](../../../src/core/utility.c#L1724),
[affect reconstruction](../../../src/magic/affects.c#L647).

## F03 — Repeated fire does not actually extend Troll-burn expiry

**Status:** source verified scheduler mismatch. **Priority:** P2.
**Recommendation:** fix.

The fire-vulnerability predicate initially creates a 30-second short affect.
Further fire only writes `af->duration`. `affect_to_char()` scheduled the expiry
event at initial insertion, and `event_short_affect()` removes the affect when
that event fires without re-reading its duration.

**Gameplay:** fire at second 0 and second 29 can still allow Troll regeneration
to return around second 30, instead of second 59. The native Troll component
changes from `10*level` to 1 before posture multipliers while burned, so this
materially weakens sustained fire counterplay. Other fire-vulnerable races get
the tag but do not enter the Troll-specific regeneration branch.

**Fix:** refresh the owning expiry event, or replace the old affect through the
existing cancellation/application machinery. Keep one burn record and one
expiry owner. Do not merely rewrite the duration field.

**Verify:** hits at 0/29 seconds, multiple hits in one pulse, removal, restoration,
and old-event cancellation; regeneration must remain suppressed until the new
deadline.
[Refresh](../../../src/combat/dam_mods.c#L385),
[event creation](../../../src/magic/affects.c#L2081),
[expiry callback](../../../src/magic/affects.c#L2011),
[regeneration](../../../src/classes/innates.c#L4871).

## F04 — Defense eligibility reads the attacker's Eyeless innate

**Status:** source verified wrong subject. **Priority:** P2.
**Recommendation:** fix.

In `pv_common(ch, opponent, ...)`, `ch` is the attacker. The block deciding
whether `opponent` can use its automatic defenses tests
`has_innate(ch, INNATE_EYELESS)` alongside `CAN_SEE(opponent, ch)` and the
opponent's blindfighting roll.

**Gameplay:** an unseen Lich/Eyeless attacker can enable its enemy's defense
checks. Conversely, the defender's own Eyeless ownership does not satisfy this
particular gate. Passing this gate only permits the subsequent defense checks;
it does not guarantee a dodge, block or parry.

**Fix:** test the defending `opponent` for Eyeless. Leave the later defense
functions' posture, immobility, equipment and skill conditions intact.

**Verify:** all four attacker/defender Eyeless combinations with failed sight
and blindfighting, then visible and immobile controls.
[Defense gate](../../../src/combat/fight.c#L11452).

## F05 — Blast becomes easier to resist as the caster gains levels

**Status:** source verified; also [stat finding F10](race-stats-issues.md#f10--innate-blast-gets-easier-to-resist-as-its-caster-gains-levels).
**Priority:** P2. **Recommendation:** fix the caller's sign.

Blast passes `max(-3,(casterLevel-targetLevel)/3)` to the victim's POW
`StatSave`. Positive modifiers help the saving character. Against level 50,
raising the Illithid from 50 to 56 changes this modifier from 0 to +2.

**Gameplay:** leveling can reduce paralysis success against the same opponent;
a weaker caster can instead make the save harder. The random one-in-three
application gate, save clamp and Quick Thinker still affect the final chance.

**Fix:** use defender-minus-caster level with the intended bounds reviewed.
Do not reverse the shared `StatSave` convention or the different `NewSaves` API.

**Verify:** equal and +/-3/6/large level gaps at fixed POW and fixed RNG;
increasing caster level must not improve the target's save.
[Blast](../../../src/classes/psionics.c#L4064),
[POW save and comparison](../../../src/core/utility.c#L3345).

## F06 — Shade Movement loses flags without losing its owning affect

**Status:** source verified lifecycle inconsistency. **Priority:** P2.
**Recommendation:** fix; settle the twilight rule in the same change.

Activation adds an unnamed, zero-type ordinary affect carrying
`AFF5_SHADE_MOVEMENT`, then sets Hide and Sneak directly. Movement/command
breaks clear the Shade Movement and Hide bits but leave the affect and Sneak.
A later recalculation can reassert the Shade Movement bit from that affect.
Ordinary expiry has no ownership information tying the direct Hide/Sneak bits
to this power. Activation permits twilight; movement treats twilight as a
reason to end the power.

**Gameplay:** the character can be told it left the shadows while retaining
stealth state or regaining the movement flag after an unrelated affect change.
This is not proof that every break immediately restores full hidden movement:
Hide is a separate bit. Twilight activation can also spend the long rest for a
power that breaks on the next step.

**Fix:** give the effect an identifiable owner and remove that effect when the
power ends. Tie its granted stealth state to its lifetime while preserving
independent Hide/Sneak sources. Use one explicit twilight policy.

**Verify:** allowed/disallowed commands, sunny/twilight/dark moves, expiry,
dispel/recalculation and relog; an ended effect must not return and independently
earned stealth must survive.
[Activation](../../../src/classes/innates.c#L3424),
[movement break](../../../src/cmd/actmove.c#L1936),
[command break](../../../src/cmd/interp.c#L2282),
[reapplication](../../../src/magic/affects.c#L647).

## F07 — Doorkick enters the destination despite promising to stay put

**Status:** source verified side effects; narrower than the reference suggests.
**Priority:** P2/P3. **Recommendation:** remove the temporary travel.

Centaur Doorkick physically removes the actor from its room, calls
`char_to_room()` on the far side to update messages/reverse door flags, then
moves back. Both insertions pass direction `-1`. Before its negative-direction
early return, `char_to_room()` still updates zone/group/light state, moves linked
riding participants, performs an automatic look and sends GMCP room updates.

**Gameplay:** a stationary door-opening action produces a far-side room view
and transient location updates, including for a carried rider. This is extra
information and state churn. **The negative direction skips ordinary entry
specials, environmental hazards and aggression:** the reference's suggestion
of normal trap/deadly-entry exposure is not supported by this call path.
The handler can return on an insertion failure, but no such live failure or
stranded character was demonstrated.

**Fix:** update the validated reverse exit directly and send the far-side message
through existing room messaging. Keep the actor in the original room. Retain
Doorbash's intentional forward movement as a separate behavior.

**Verify:** two-sided/one-sided doors, mismatched reverse exits, automatic-look
and GMCP output, carried riders, unchanged room membership, self-damage and lag.
[Doorkick](../../../src/classes/innates.c#L4201),
[real room insertion and early return](../../../src/world/handler.c#L1617).

## F08 — Giant Avoidance can make an intermediate dodge score worse

**Status:** source verified arithmetic; final effect is conditional. **Priority:** P2.
**Recommendation:** fix the negative-score behavior; retain the current race list.

Mountain Dwarf's bonus multiplies `agilityScore - attackerWeaponSkill` by 1.10
before later stat/level additions and the final clamp. If that intermediate
score is negative, the supposed bonus makes it more negative.

**Gameplay:** for example, an intermediate -20 becomes -22; a later +30 gives
8 instead of 10 before clamps. Where the floor does not mask it, owning the
defensive innate can reduce avoidance against Troll/Ogre/Giant attackers.

**Fix:** ensure the bonus never reduces the score, preferably by applying its
percentage only to a nonnegative eligible component. Specify the intended
calculation before moving it to an entirely different stage.

**Verify:** negative/zero/positive intermediate scores, floor/cap boundaries and
matched attackers. Expanding the list to Storm Giant/Snow Ogre would be a
separate balance change; their omission alone is not a proven bug.
[Consumer](../../../src/combat/fight.c#L9376).

## F09 — A Forest Sight item can reduce racial Forest Sight

**Status:** source verified; item flag has an active grant path. **Priority:** P2.
**Recommendation:** fix the downgrade.

Grey Elf, Wood Elf and Firbolg's innate bypasses the range-3 forest cap.
The later `AFF5_FOREST_SIGHT` branch assigns `n=5` unconditionally. The flag is
not only a hypothetical temporary spell: the epic-store grant path sets it on
an object.

**Gameplay:** a character whose racial sight preserves range 8 can drop to 5
when adding a forest-sight item, before the later perception/altitude additions.
A beneficial item can therefore reduce map information.

**Fix:** make the item flag establish a minimum forest range of 5 rather than
overwriting a better existing range, if that is the intended bonus. Preserve
Eyeless's separate explicit early-return contract.

**Verify:** native Forest Sight on/off, starting ranges below/equal/above 5,
day/night, item equip/remove, perception and altitude.
[Map ordering](../../../src/world/map.c#L1317),
[item grant](../../../src/economy/tradeskill.c#L101).

## F10 — Some deterministic refusals still spend long cooldowns

**Status:** source verified. **Priority:** P2 for avoidable refusals.
**Recommendation:** move known preconditions before consumption selectively.

The five cases listed as resolved below are fixed, but these remain:

- **Ogre Roar:** missing target, prohibited size/state, silence, existing roar
  and other admission failures follow the timer. An ordinary Ogre can lose
  its default 720-second use without a valid attempt.
- **Blast:** a shopkeeper is ignored after spending the use.
- **Globe of Darkness:** existing globe/Mage Flame conflicts are inside the
  called spell, after consumption.
- **Battle Rage:** already hasted does nothing after consumption. Removing
  Slow is a useful result and should continue to cost a use.
- **Stone Skin:** incompatible existing skin can reject after its 300-second
  use is spent; preserve class-specific stacking exceptions.
- **Horde/Warg:** some already-invalid rooms or existing capacity constraints
  are deferred until arrival. Horde even warns about single-file terrain
  after consumption while still scheduling the event.
- **Travel/Darkness:** inner travel wards and already-dark rooms can absorb a
  use. Some of these may deliberately charge for an attempted action.

**Gameplay:** avoidable mistakes or redundant buffs cause minutes of downtime;
failure ordering varies across otherwise similar racial powers.

**Fix:** preflight cheap, already-known refusals. Keep charges for valid attacks
that miss, are resisted or evaded, and normally for a summon whose destination
becomes invalid after dispatch. Do not add blanket refunds or make all failed
actions free. Decide travel and light-cancellation costs explicitly.

**Verify:** each preflight refusal with no timer and with multiple uses remaining;
successful/defended attempts; room changes during a delayed summon.
[Roar](../../../src/classes/new_skills.c#L3425),
[Blast](../../../src/classes/innates.c#L2626),
[Globe](../../../src/classes/innates.c#L3042),
[Battle Rage](../../../src/classes/innates.c#L3269),
[Stone Skin](../../../src/classes/innates.c#L3360),
[Warg](../../../src/classes/new_skills.c#L3171),
[Horde](../../../src/classes/new_skills.c#L3302).

## F11 — Generic innate status misses Charge and Call of the Grave rests

**Status:** source verified presentation mismatch. **Priority:** P2/P3.
**Recommendation:** fix the status lookup.

`innate_status()` and `can_use_innate()` inspect `TAG_INNATE_TIMER`. Minotaur
Charge and Lich Call of the Grave instead use `SKILL_CHARGE` and
`SKILL_CALL_GRAVE` affects. The info/list path has no special handling for them.

**Gameplay:** the command can report an innate as ready while its actual handler
rejects it for resting: 12 seconds after a Charge hit, or 240 seconds for Grave.
This can mislead a player choosing an opener or summoning reinforcements.

**Fix:** consult each action's actual rest source when displaying availability;
do not introduce a second cooldown merely to satisfy the display.

**Verify:** before use, during rest, after expiry and after restoration for both
skills, plus an ordinary generic-timer innate.
[Status](../../../src/classes/innates.c#L1157),
[generic readiness](../../../src/classes/innates.c#L1135),
[Charge rest](../../../src/cmd/actoff.c#L1555),
[Grave rest](../../../src/cmd/actoff.c#L12799).

## F12 — Horse/Spider Body makes Trip's size window impossible

**Status:** source verified contradiction; overlaps size F03. **Priority:** P2.
**Recommendation:** resolve the intended body rule.

Trip first requires the attacker to be strictly larger than a Horse/Spider Body
target, then rejects a victim smaller than the attacker. No size pair can pass
both checks. Centaur and Drider therefore receive effective Trip immunity,
rather than merely requiring a larger tripper.

**Gameplay:** growth cannot let the attacker solve the restriction; attempts
can sit the actor and cost tempo. This also makes race comparisons based on
ordinary size windows misleading.

**Fix:** prefer the explicit early body rule and allow the intended larger-actor
window, or explicitly declare immunity if that is the design. This changes
current immunity and warrants a gameplay decision. Exhaust all size pairs and
preserve the ordinary humanoid window.
[Early condition](../../../src/cmd/actoff.c#L12409),
[contradicting later condition](../../../src/cmd/actoff.c#L12456),
[size finding](race-size-issues.md#f03--trip-has-an-impossible-body-size-window).

## F13 — NPC body eligibility disagrees with the actions it selects

**Status:** source verified; overlaps size F04–F06. **Priority:** P2.
**Recommendation:** align each helper with its owning action.

`isBashable()` checks Horse Body but omits Spider Body; actual Bash checks both.
`isSpringable()` rejects equal Horse/Spider targets that actual Springleap can
admit and rejects ground elevation outright. Gaze AI also imports Bash's body
and size restrictions through `isBashable()` despite being a different action.

**Gameplay:** Driders/Centaurs receive inconsistent NPC counterplay: an NPC can
select a doomed control action, fall/pay lag, or skip a legal one. Gaze users
can incorrectly avoid a legal body/size target. The recently corrected Bash
quadruped subject does not repair these helper mismatches.

**Fix:** use each command's actual admissible body/size/footing conditions for
its AI eligibility; keep tactical preferences distinct from hard rejection.

**Verify:** all body/size pairs, ground elevation, NPC preparation/posture changes,
and actual command outcomes. See the companion for the wider size audit.
[Bash helper](../../../src/cmd/actoff.c#L8323),
[Springleap helper](../../../src/cmd/actoff.c#L13911),
[Gaze selection](../../../src/mob/mobact.c#L5507),
[size findings](race-size-issues.md#f04--npc-springleap-eligibility-contradicts-the-command).

## F14 — Innate Enlarge can block a later spell's stat package

**Status:** source verified; overlaps size F10. **Priority:** P2, intent-sensitive.
**Recommendation:** define replacement/upgrade behavior.

Duergar/Shadow Beast's innate applies `SPELL_ENLARGE` with the size bit and no
STR/CON/AGI/DEX package. The ordinary Enlarge spell checks for that spell type and can
skip its own package when the innate is already present. The recent fix to
rejected innate-use costs does not change this shared effect identity.

**Gameplay:** innate-first and spell-first orders can leave different stats
despite both being described as Enlarge. Casting the spell later is not
necessarily an upgrade to the full spell effect.

**Fix:** specify whether the stronger/different spell replaces the innate, or
whether all versions intentionally exclude one another. Preserve exactly one
size increment and coherent expiry; do not simply permit both full packages.

**Verify:** both application orders, refresh, Reduce/Titan interactions and
expiry/recalculation.
[Innate](../../../src/classes/innates.c#L2818),
[spell](../../../src/magic/magic.c#L23120),
[detailed size finding](race-size-issues.md#f10--innate-enlarge-makes-a-later-spell-skip-its-stat-package).

## F15 — Shape ownership and innate payload use different race identities

**Status:** source verified inconsistency; exposure conditional on obtainable
forms. **Priority:** P2/P3. **Recommendation:** decide per ability, then align.

`has_innate()` normally uses a shape disguise's race. Other consumers use the
mechanics/native race: racial shrug magnitude, Prime Shift's destination switch,
Horde's explicit Orc restriction, and Ogre/Firbolg Magic Vulnerability.
Bite instead dispatches variants with `GET_RACE2`. Roar advertises a native
Ogre restriction that its handler does not enforce.

**Gameplay:** a form can advertise access yet receive another body's magnitude,
be refused, or lack a return route selected by native race. Conversely, some
native vulnerabilities may not follow an acquired innate. Not every PC race is
an obtainable shape; this is not a claim that all combinations are exploitable.

**Fix:** document whether each rule follows native identity or current body.
Make access, facts and payload agree for supported combinations. Reject an
unsupported travel variant before spending its use. Avoid globally replacing
all race reads, which would change unrelated racial behavior.

**Verify:** actual learnable shapes, native and shaped holders/nonholders,
enter/leave form, outgoing/return travel, and any supported stored race change.
[Ownership](../../../src/classes/innates.c#L381),
[shrug](../../../src/classes/innates.c#L4907),
[Prime selection](../../../src/classes/innates.c#L2603),
[Horde](../../../src/classes/new_skills.c#L3302),
[vulnerability](../../../src/combat/dam_mods.c).

## F16 — Summon Totem uses logical OR for string-ownership flags

**Status:** source verified defect found while following totem creation.
**Priority:** P2. **Recommendation:** fix.

`SET_BIT(totem->str_mask, STRUNG_DESC2 || STRUNG_KEYS)` evaluates the operand to
1 instead of combining both flags. The handler allocates a personal name and
short description. `free_obj()` only releases the short description when
`STRUNG_DESC2` is recorded.

**Gameplay:** repeated replacements can retain an allocated personal short
description when the template did not already mark it as owned. There is no
immediate combat bonus; this is avoidable server memory/ownership damage in a
no-rest summon path. Its observed magnitude was not measured on a running MUD.

**Fix:** use bitwise OR and follow the existing ownership convention for replacing
prototype versus already-owned strings. Check serialization as well as freeing.

**Verify:** repeated summon/replace/extract under leak checking, with shared
template strings and already-owned strings; both new strings must have the
correct ownership bits.
[Creation](../../../src/classes/new_skills.c#L2722),
[flag definitions](../../../src/core/defines.h#L376),
[freeing](../../../src/world/db.c#L4612).

## F17 — Totem level gates depend on inherited prototype fields

**Status:** conditional content-contract risk. **Priority:** P3.
**Recommendation:** inspect the prototype and define which fields are tier-owned.

The Goblin summon clears only `bitvector`, then adds tier flags and selected
affect slots. Higher bitvectors and untouched affects are inherited from object
417. It does not clear Soulshield or higher-tier stat slots below their unlocks.

**Gameplay:** a changed prototype containing a higher-tier property can give it
to a low-level Goblin despite the apparent 31/36/41/51/56 progression. Conversely,
overwriting a tier slot can erase a template property at higher levels. No live
SQL prototype was inspected, so a currently obtainable extra bonus is unproven.

**Fix:** preserve intended template anatomy/wear rules and base bonuses, but
initialize fields owned by the tier system deterministically. Do not wipe every
template flag as an indiscriminate repair.

**Verify:** a deliberately nonempty template at each boundary, replacement
failure, and actual equipped effects. The established replacement path already
prevents treating every cast as an unlimited stack of personal totems.
[Tier construction](../../../src/classes/new_skills.c#L2710),
[legacy prototype](../../../areas/obj/heavens.obj#L4389).

## F18 — Gambler's Luck bypasses the common effective-stat cap

**Status:** source verified; overlaps stat F18. **Priority:** P3, balance decision.
**Recommendation:** make the exception explicit or clamp after the bonus.

Halfling's +10 Luck is applied after the ordinary 1..511 clamp, permitting 521.
It does not repeatedly accumulate on recalculation.

**Gameplay:** sufficiently high-Luck builds can exceed the shared cap in raw
Luck consumers, though indexed/capped consumers may gain nothing further.
This is not evidence that every Halfling build can reach the boundary.

**Fix:** if 511 is universal, apply the bonus before the final clamp. If this is
an intentional racial exception, document it and check consumers for that range.
Do not remove the +10 racial benefit at ordinary values.

**Verify:** 500/501/510/511 inputs, repeated recalculation, raw and indexed uses.
[Addition](../../../src/magic/affects.c#L1034),
[stat finding](race-stats-issues.md#f18--gamblers-luck-bypasses-the-effective-stat-cap).

## F19 — Dayvision is listed as a passive but has no gameplay consumer

**Status:** source verified missing consumer. **Priority:** P3.
**Recommendation:** clarify/retire the redundant marker unless a mechanic is intended.

Orc, Minotaur, Thri-Kreen, Harpy, Githzerai and Kobold list Dayvision. Source
references assign/name/display it, but it does not cancel Dayblind or grant a
daylight defense. These races generally lack Dayblind independently.

**Gameplay:** players can count a nonexistent active advantage when comparing
races or interpreting sunlight weaknesses. Removing the marker alone would not
make its holders blind, and keeping it does not protect from sun damage.

**Fix:** describe it as informational or remove redundant presentation after a
compatibility check. Only implement Dayblind cancellation or another bonus if
that is the chosen design; adding it is a balance change.

**Verify:** enumerate every reference and confirm race help/catalog behavior;
test an intentionally combined Dayblind/Dayvision case if cancellation is added.
[Assignments/catalog](../../../src/classes/innates.c),
[Dayblind predicate](../../../src/core/utils.h#L1217).

## F20 — Dayblind, character sight, and sight descriptions disagree

**Status:** source verified mismatch; restoration of old rules is a design decision.
**Priority:** P3. **Recommendation:** correct facts, then decide sight policy.

Planetbound Illithid is the current native PC Dayblind holder. Some historical
character-sight rejection branches were disabled, while map and directional
sight penalties remain. Current Dayblind facts still promise only red shapes
with infravision and no sight without it, which is stronger than the character
visibility implementation.

**Gameplay:** room targets, map range and adjacent-room information need not
agree with the player's understanding of blindness. Re-enabling the old blanket
checks would substantially change exploration and target acquisition.

**Fix:** update facts to describe current separate consumers. If a single light
policy is desired, specify it first, covering infra-invisible races, Eyeless,
globe/Mage Flame and object versus character sight.

**Verify:** lit/dark/twilight rooms and maps, with/without infra, another occupant's
globe, invisible targets and directional look. Do not equate Dayblind to `AFF_BLIND`.
[Character sight](../../../src/core/utility.c#L1791),
[facts/map](../../../src/world/map.c#L1200),
[directional look](../../../src/cmd/actinf.c#L2841).

## F21 — Sun burn, HP recovery, and mana recovery have different exemptions

**Status:** source verified; design consistency question. **Priority:** P3.
**Recommendation:** specify the differences or deliberately unify them.

Forest/swamp and Bloodlust exemptions exist for periodic burn. HP recovery has
a magic-dark exception; mana/PSP recovery does not. Twilight and a personal
globe are handled by their respective checks. Avoiding visible burn does not
establish that either recovery resource is allowed.

**Gameplay:** a sun-vulnerable character can stop taking burn yet still fail to
recover, or recover HP in magical darkness while mana stays blocked. Terrain
outcomes also depend on `IS_SUNLIT`, not solely the sector's name.

**Fix:** decide which sources of shelter protect which resources. Prefer an
accurate description over silently granting universal recovery protection.
If the exemptions were meant to agree, apply the chosen policy consistently.

**Verify:** sun/time, forest/swamp, twilight, magical darkness, personal/other
globe and Bloodlust, checking all three outcomes independently.
[Burn](../../../src/world/handler.c#L477),
[HP](../../../src/world/limits.c#L418),
[mana](../../../src/world/limits.c#L161).

## F22 — Rrakkma's AC scaling has no shrug-style holder cap

**Status:** source verified; design decision. **Priority:** P3.
**Recommendation:** decide the cap and contributor-state contract.

Githzerai's shrug counts at most five other eligible holders under committed
settings. AC deducts 10 for every other grouped PC holder in the room, with
only the final overall AC clamp. Neither count explicitly requires a conscious,
standing participant.

**Gameplay:** six other holders give -60 AC but the same +25 shrug as five.
Incapacitated group members can still contribute while satisfying the existing
room/group/ownership conditions. Large homogeneous groups get a different
scaling curve for the two benefits.

**Fix:** if both bonuses are supposed to share a five-holder limit, apply it to
AC too; otherwise document uncapped AC. Decide whether passive presence or active
participation is intended before adding posture restrictions.

**Verify:** 0/1/5/6+ other holders, membership/room changes, unconscious members,
and the final AC clamp. No current rule proves that the two caps must match.
[Shrug](../../../src/classes/innates.c#L4919),
[AC](../../../src/combat/fight.c#L6782),
[settings](../../../lib/duris.properties#L1965).

## F23 — Warcaller's Fury scales from the victim's group and reaches spells

**Status:** source verified; design decision, not a wrong-subject conclusion.
**Priority:** P3. **Recommendation:** preserve until its design is clarified.

Orog Fury's first count uses the victim's other grouped PCs in the room. Its
second uses the attacker's other Fury holders, capped at 10 by committed
configuration. It modifies raw damage, which receives ordinary spell as well
as melee deliveries.

**Gameplay:** fighting a larger enemy group increases the Orog's own damage;
an Orog caster can benefit too. With level 56 and the configured holder cap,
the combined predicate bonus can reach about 48.33% before downstream rules.
That is not a party-wide aura or strictly a weapon bonus.

**Fix:** verify that anti-group scaling and spell applicability are intended.
If the design is an allied melee warband bonus, change the owning count/delivery
gate and retune deliberately. Do not automatically swap victim for caster
because another finding contains a genuine wrong-subject bug.

**Verify:** victim-group versus actor-group matrices, mixed races, holder cap,
melee/spell delivery and raw-damage exceptions.
[Modifier](../../../src/combat/dam_mods.c#L999),
[group count](../../../src/guild/group.c#L1137),
[setting](../../../lib/duris.properties#L1967).

## F24 — Swamp Sneak also satisfies boat admission outside swamps

**Status:** source verified; design decision. **Priority:** P3.
**Recommendation:** document the swimming benefit or separate its condition.

The boat-admission branch checks innate ownership, without checking swamp/slime
terrain. Troll from 11 and Kuo Toa from 1 can satisfy that branch on other
water terrain. Stealth and map suppression use narrower terrain predicates.

**Gameplay:** a stealth unlock can also change water-route access. This does not
grant underwater breathing: Kuo Toa's Waterbreath still waits until 15, and
other drowning/current/footing checks remain.

**Fix:** preserve and document broader swimming access if intended. If the
ability should only assist swamp travel, gate that benefit accordingly and
review legitimate Kuo Toa water access separately.

**Verify:** swamp/slime, river/lake/ocean and underwater movement before/after
unlock, with breathing and boat requirements tested separately.
[Boat admission](../../../src/cmd/actmove.c#L958),
[terrain sneak](../../../src/core/defines.h#L1385),
[map suppression](../../../src/world/map.c#L703).

## F25 — Summon Warg inherits class variants and level-51 flight

**Status:** source verified; design decision. **Priority:** P3.
**Recommendation:** decide what the racial summon promises.

Orc's innate invokes the general mount arrival routine. Class branches can
select a knight mount before the Orc/Goblin warg branch, and the general
`level > 50` condition grants Fly even to an ordinary warg.

**Gameplay:** a high-level Orc can obtain flying-mount travel without that being
obvious from the racial innate's name; some legal class/race combinations can
summon a different mount with class-specific benefits. This is verified code,
not proof that the generic rule was accidental.

**Fix:** if the racial power means a ground warg, select that variant and apply
its movement package explicitly. Otherwise document flight and class precedence.
Do not remove intended knight-mount powers as collateral damage.

**Verify:** ordinary Orc at 50/51/56, relevant permitted classes/specs, existing
mount refusal and resulting flight after recalculation/restoration.
[Selection](../../../src/classes/new_skills.c#L2820),
[flight](../../../src/classes/new_skills.c#L2929),
[racial call](../../../src/classes/new_skills.c#L3171).

## F26 — Regeneration's combat benefit depends on affect representation

**Status:** source verified; design decision. **Priority:** P3.
**Recommendation:** establish whether racial and spell regeneration should differ.

For a fighting character, HP recovery looks for an actual affect containing
`AFF4_REGENERATION`. Finding one avoids the passive-only halving branch. Troll
and Revenant's innate reasserts the same bit without itself supplying such an
affect. Their racial multiplier selection can already supersede the ordinary
regeneration-spell multiplier.

**Gameplay:** casting Regeneration on a racial regenerator can improve combat
recovery by changing its representation even without adding another racial
multiplier. The halving affects the calculated gain, not just the innate
component; sunlight, swimming and other blockers still win.

**Fix:** retain and describe the spell's additional combat benefit if intentional.
If the same regeneration state is supposed to be equivalent, use an explicit
mechanical policy rather than whether a matching affect record happens to exist.

**Verify:** Troll/Revenant with innate alone, spell alone where applicable and
both, fighting/resting, burn, sunlight and no-heal conditions.
[Combat recovery](../../../src/world/limits.c#L389),
[racial helper](../../../src/classes/innates.c#L4859),
[passive bit reconstruction](../../../src/magic/affects.c#L768).

## F27 — Catalogs, descriptions, and dormant code can imply nonexistent powers

**Status:** presentation/dormant; no automatic balance fix. **Priority:** P3.
**Recommendation:** correct descriptions and retire dead paths carefully.

- `innate list player` uses a hard-coded historical exclusion list, not all PC
  IDs or current creation policy. A player can miss restricted-race information;
  the list also does not exactly mean the ordinary creation roster.
- Roar's facts say only a plain Ogre may use it, but admission uses ownership.
  Shade Movement's facts overstate which commands break it.
- Orc's Warg assignment sits in the Goblin comment block. Moving the comment or
  assignment for clarity must not accidentally grant Warg to Goblin.
- PC Vampire has no Gaze grant. Its old Bite heal/charm block is after an
  unconditional return and is unreachable. Do not promise those rewards or
  revive the block as a cleanup.
- Storm Giant has no current racial grants; commented doors/vision/lightning,
  and removed Halfling/Drider/Drow innates, are not active bugs by themselves.
- `get_level_from_innate()` retains different historical lookup rules but no
  active caller was found. Keep it out of new access paths or retire it; current
  specialization ownership uses the newer lookup.
- Corpseform's entry remains disabled. Its old innate-mode/storage problems
  belong to a re-enablement prerequisite, not a currently usable racial power.

**Gameplay:** incorrect expectations affect race/build choices and commands;
future maintenance can accidentally restore retired powers or wrong unlocks.

**Fix:** derive list membership from the intended PC/creation policy, update facts
from executable behavior, and delete dormant implementations only after checking
callers and persistent identifiers. Do not renumber saved innate IDs.

**Verify:** all 37 PC IDs, ordinary/restricted filters, shape descriptions,
active grants and generated help; no gameplay change from documentation cleanup.
[List filter](../../../src/classes/innates.c#L6555),
[Roar facts](../../../src/classes/new_skills.c#L3418),
[Vampire Bite dispatch](../../../src/classes/innates.c#L2160),
[old lookup](../../../src/classes/innates.c),
[disabled corpseform and prior finding](race-size-issues.md#f21--dormant-corpseform-overwrites-its-innate-mode-marker).

## Resolved since the reference snapshot

Do not file these as open defects based on the older reference:

- **Leap's unlock/catalog mismatch:** `leapSucceed()` now uses `has_innate`;
  Thri-Kreen unlocks at 21 and Harpy has an explicit level-1 grant. Gargoyle also
  receives a level-1 grant outside the PC census. The PC matrix is therefore
  **189 grants**, up from the reference's 188; still 37 PC races and 78 distinct
  PC-granted innate IDs. Fixed in `159d29778`.
- **Five rejected-use costs:** out-of-combat Throw Lightning, aboveground
  Underdark Invisibility, existing Strength, existing Enlarge/Titan, and Horde
  off-prime/on-ocean now reject before spending a use (`159d29778`). Enlarge
  retains its explicit refusal lag. Other cases remain under F10.
- **Bite configuration key:** the helper now reads `innate.timer.secs.bite`,
  matching the committed property (`6a88d0c1f`). The default remains 12 seconds;
  the old mismatch is no longer a tuning defect here.
- **Ogre Roar's mixed-subject worst result:** both AC and hitroll penalties now
  apply to the actor, and facts say so (`d77db6254`). The old target-AC/actor-hitroll
  outcome is obsolete. Its admission/cost and description issues remain separate.
- **Bash's quadruped subject:** the two Bash checks now use the victim's race
  (`159d29778`). This does not resolve the other body/AI contradictions in
  F12/F13 or every related condition discussed in the size companion.

The supplied reference has not been edited as part of this requested companion.
Its roster, affected ability sections, reuse table and mismatch summary need
these corrections before being used as a statement of current behavior.

## Reviewed observations that do not yet justify a bug fix

- **Project Image does have downstream cleanup.** Mobile 250 is assigned
  `imageproc`; an idle uncharmed image is extracted on its periodic call.
  The innate removes its initial affects, so a normal idle projection meets
  that cleanup condition. The proc skips fighting images, and actual runtime
  assignment still matters. Do not infer permanent unlimited images solely
  from the handler's lack of a timer/count limit.
  [Assignment](../../../src/specs/specs.assign.c#L460),
  [cleanup](../../../src/specs/specs.mobile.c#L11959).
- **Repeated cold Slow affects are not multiplicative slowdowns.** The cold
  vulnerability adds separate 15-second records, but their common bit does not
  multiply attack penalties; `affect_from_char(SPELL_SLOW)` removes all matching
  records. Coalescing must preserve refresh/expiry and interaction with a longer
  ordinary Slow. No additional stacking exploit was established.
  [Application](../../../src/combat/dam_mods.c#L727),
  [bulk removal](../../../src/magic/affects.c#L2352).
- **Cooldown persistence is not a logout reset.** Generic timers are saved short
  affects and do not request offline advancement. Whether rest should count
  offline is a product choice. Describe it, and test a live relog before claiming
  a persistence defect. First-use-window recharge for multiple uses is also an
  implemented policy, not an off-by-one finding here.
  [Timer flags](../../../src/classes/innates.c#L1229),
  [snapshot](../../../src/player/player_snapshot_capture.c#L300),
  [offline gate](../../../src/account/nanny.c#L1773).
- **Hatred from visible friendly/NPC races, global primary-weapon mastery
  bonuses, class-dependent spell payloads, Spell Absorb needing spent slots,
  no-rest Faerie Fire/Firestorm/Fireshield, grave-wave overlap and personal
  totem replacement** all have explicit implementations. They may be balance
  topics, but this review found no contradiction proving they should be changed.
  Likewise, Disappear does not promise to clear an existing combat target, and
  Burrow currently means Hide rather than literal terrain traversal.
- **Existing active effects and equipment surviving a race/form change** are
  not universally erroneous: spells, items and pets have their own lifetimes.
  Temporary-race persistence and missing restoration state are separately
  analyzed in [size F02](race-size-issues.md#f02--temporary-race-can-be-saved-without-its-restoration-state);
  do not conflate that identity problem with every retained buff.

## Verification and limits

The review read the complete racial-innate reference, followed suspicious
handlers into their consumers/lifecycle code, searched for passive consumers,
and compared the reference revision with the current source. Recommendations
above are source findings, not newly reproduced live gameplay incidents.

These focused local checks passed:

- `python3 tests/async/test_innate_action_dispositions.py`: rejected uses,
  remaining charges, valid costs, Leap levels and mount HP under sanitizers.
- `python3 tests/async/test_innate_specialization.py`: lookup, restoration and
  snapshot checks under ASan/UBSan.
- `python3 tests/async/test_race_innate_help_sync.py`: four help synchronization
  checks.
- `python3 tests/async/test_ability_innates_1.py` and
  `python3 tests/async/test_ability_innates_2.py`: innate facts/numeric contracts.
- `python3 tests/async/test_low_combat_dispositions.py`: including the corrected
  Ogre Roar recipients.

Those checks support current contracts and the resolved distinctions; they do
not reproduce every open finding. An independent comment-stripped assignment
enumeration confirmed 189 PC grants and 78 distinct PC innate IDs. All 27 finding
IDs, local links/anchors and document whitespace were checked.

Documentation-only work requires no server build. No server was started or
stopped, no production operation or live SQL prototype inspection was performed,
and no gameplay fix, commit, push, or issue filing is part of this report.

Live configuration, world assignments, obtainable forms/items and actual PvP
frequency remain unmeasured. Each proposed gameplay change should use the
entry's focused regression cases plus an appropriate local gameplay journey.
