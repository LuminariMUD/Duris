# Race combat resolution: potential bugs, gameplay impact, and recommended fixes

Source review: 2026-11-08, checkout `afdd1fd4a40f27e5cc3f7686dcbb3de9f0ec2318`.
Companion to [race-combat-resolution.md](race-combat-resolution.md). This is an
audit of the paths exposed by that analysis, not a claim to have found every
possible defect in the game. No gameplay code was changed.

The report separates reproduced implementation defects, conditional paths,
retained behavior requiring a balance decision, and observations that do not
establish a bug. Existing stats/size/innate/tempo findings are cross-referenced
below rather than counted again as new discoveries. Restricted-race behavior
is labelled where relevant; a test fixture does not prove an obtainable build
or a deployed exploit.

## Evidence and recommended order

- **P1:** repair terminal-action/lifecycle handling first: feeding, word
  banishment, and the nested Ethereal Alliance damage boundary (F01–F03).
- **P2:** repair clear wrong-subject, wrong-sign, order-dependent, miswired
  configuration and threshold defects (F04–F10). Resolve actual negations and
  prohibited actions before changing ordinary mitigation (F11–F13).
- **P3/conditional:** fix ward accounting if the multiple-provider path is
  retained, and make damroll-cap rounding explicit (F14–F15).
- **Decision required:** parry's retained random-roll behavior, Sanctuary's
  class policy, and vamp priority (F16–F18) need an explicit intended contract.
  Do not use these reviews to silently rebalance every race or class.

“Reproduced” below means an isolated fixture executing the current production
function, predicate or relevant block with real engine types and controlled
dependencies. It does not mean a live server/player reproduction. Where a
damage response or scheduler is an adapter, that limitation is stated.

## F01 — Illithid feeding can bypass protection and kill a recovered target

**Status:** P1, reproduced command/callback defect; original Illithid only.

**Evidence:** `do_drain()` checks original Illithid race, target presence,
non-self and status below sleeping, then schedules `event_illithid_feeding`.
It does not run hostile-action/safe-room/protected-target admission. Its
`CMD_N` registration prevents starting while fighting; it is not a substitute
for those target checks. The callback checks pointers and co-location, then
restores mana and calls `die()` without rechecking the target's incapacity or
the action's continuing legality. The fixture scheduled feeding in a safe
room, restored the target to normal standing status, and still reached the
death call after the scheduled 28 pulses for a level-56 target.
[Command and callback](../../../src/classes/psionics.c#L73),
[registration](../../../src/cmd/interp.c#L3208),
[command registration semantics](../../../src/cmd/interp.c#L2920).

**Gameplay:** a protected incapacitated character can be selected through this
handler; healing the victim before completion does not save it if it remains
in the room. Original Illithid gets mana restoration from a kill that may no
longer satisfy the feeding conditions. Planetbound Illithid does not pass the
original-race gate.

**Fix:** use existing hostile-action/protection admission at initiation and
completion. At completion validate both participants, current location and
continued incapacity before restoring resources or killing. Define cancellation
on recovery explicitly; ensure repeated initiation cannot leave duplicate work.

**Verify:** safe/protected/consenting-but-not-hostile targets; ordinary eligible
NPC; recovery, movement, extraction and caster death during the delay; repeated
commands; no resource reward when the final action is refused.

## F02 — Word spells attempt banishment after terminal damage

**Status:** P1, reproduced continuation defect; actual deallocation/crash not
claimed by this fixture.

**Evidence:** the ordinary-level branches of `single_holy_word`,
`single_unholy_word` and `single_voice_of_creation` check the damage result for
their blindness/paralysis block, but call `astral_banishment()` afterwards
unconditionally. The helper does not begin with an alive-participant check.
The Holy Word fixture returned `DAM_VICTDEAD` and `DAM_CHARDEAD` separately;
both still invoked banishment with a terminal participant.
[Holy Word](../../../src/magic/magic.c#L19919),
[Unholy Word](../../../src/magic/magic.c#L19760),
[Voice of Creation](../../../src/magic/magic.c#L19852),
[banishment helper](../../../src/magic/magic.c#L19127).

**Gameplay:** the Githyanki/Githzerai banishment path can run after a fatal
strike or a reflected attack that kills the caster. Depending on death cleanup,
this risks moving a dead/respawned participant or using invalid state. The
ordinary successful-damage case is not the problem.

**Fix:** capture the result once and stop on any terminal outcome. Revalidate
participant identity/location after callbacks before secondary movement, using
the existing continuation conventions. Do not inspect potentially freed
pointers as the only lifetime safeguard.

**Verify:** each word with target death, caster death from reflection, both
dead, target movement and normal survival; only the surviving, still-eligible
case may attempt banishment. Include real-release fixtures as well as markers.

## F03 — Ethereal Alliance discards the outcome of nested damage

**Status:** P1 conditional lifecycle risk; ignored outcome reproduced, live
death/proc sequence not reproduced.

**Evidence:** the spell modifier predicate calls `raw_damage` on the linked
partner and ignores its return, then supplies the original target's -.50 More
modifier. Its caller continues through later predicates and original delivery.
A fixture whose nested damage marked the caster dead and returned
`DAM_CHARDEAD` still completed the predicate normally with that modifier.
[Alliance predicate](../../../src/combat/dam_mods.c#L819),
[outer modifier loop](../../../src/combat/fight.c#L4822),
[alliance setup](../../../src/classes/ethermancer.c#L2588).

**Gameplay:** when linked damage or its death callbacks invalidate the caster
or original target, the outer spell can continue with stale participants.
This is distinct from the valid case where only the linked partner dies and
the remaining participants are still safe to process. Races with different
HP, healing and defenses change how often lethal sharing is encountered.

**Fix:** make the nested delivery an explicitly checked step, propagating
terminal outcomes or validating captured participant identities before the
outer pipeline resumes. Preserve the intended split when the partner alone
dies; do not solve this by suppressing all remaining damage indiscriminately.

**Verify:** partner survival/death, caster death or movement during nested
delivery, original-target extraction, and unchanged ordinary split amounts.

## F04 — Orc's horde defense increases incoming damage

**Status:** P2, reproduced arithmetic defect; room population policy is a
separate design choice.

**Evidence:** the defensive branch counts Orcs negatively, adds one to remove
self, then returns `damage*(1-c/100)`. The two negatives turn the intended
defensive direction into an increase. With one other Orc, 1000 becomes 1015;
with five, the factor is 1.075. `hit()` chooses attacker-Orc or defender-Orc via
`if/else if`, so an Orc attacker prevents the defender branch from running.
[Helper](../../../src/combat/fight.c#L11975),
[dispatch](../../../src/combat/fight.c#L8665),
[setting](../../../lib/duris.properties#L618).

**Gameplay:** gathering Orcs, including the fragile summoned horde, increases
the ordinary-hit damage an Orc takes from a non-Orc. Other Orcs can be enemies
or unrelated NPCs because friendliness/ownership is not checked. This can
reverse the expected value of the race's group mechanic.

**Fix:** count other eligible Orcs positively and apply the chosen defensive
reduction once. Define and bound the intended population and minimum factor.
Decide independently whether both sides' modifiers should apply Orc-versus-Orc;
do not bundle a new group-only rule into the sign correction without stating it.

**Verify:** zero/one/five others, summoned NPCs, enemy Orcs, non-Orc attackers,
Orc-versus-Orc and the chosen reduction floor.

## F05 — Monk pressure-point cleanup removes the attacker's tag

**Status:** P2, reproduced wrong-subject defect.

**Evidence:** `monk_critic()` reads/increments `TAG_PRESSURE_POINTS` on the
victim, but at count 6 calls `affect_from_char(ch, TAG_PRESSURE_POINTS)`. The
fixture left the victim's counter at 6 and removed a tag from the attacker.
[Pressure-point sequence](../../../src/combat/fight.c#L7010).

**Gameplay:** the target's sequence does not reset as the sixth-hit cleanup
suggests; subsequent increments miss the 2/3/4/5 effect cases until expiry.
If the attacker is also carrying an opponent's pressure-point tag, its own
attack can remove that incoming progression instead. Eligible Monk builds
lose control/damage consistency, and mutual-Monk fights acquire a wrong-owner
interaction.

**Fix:** remove/reset the owning victim's sequence. Keep the current timing
and sequence effects unless a separate balance decision changes them.

**Verify:** hits 1–7, expiry and restart, both participants carrying counters,
and target death during the fifth-stage damage callback.

## F06 — Battletide makes undead self-healing depend on group-list order

**Status:** P2, reproduced dispatch defect for a native undead holder with
the relevant buff and flags.

**Evidence:** the Battletide loop assigns `vamped = vamp(tch,...)` for each
eligible ally. The later native-undead self-heal is gated on `!vamped`, so
the last ally's actual healing overwrites the outcome of earlier allies.
With the same one injured and one full-health ally, reordering the list changed
the holder's healing from 75 to 0 on a 100-damage hit, while the injured ally
received 40 in both cases.
[Battletide and subsequent undead route](../../../src/combat/fight.c#L6080).

**Gameplay:** identical groups and attacks produce different personal sustain
depending on list order and the last ally's HP. Full-health allies can enable
additional healing rather than merely declining their own share. This affects
the eight native undead PC races when the required state is available.

**Fix:** distinguish personal vamp state from healing other recipients, or
aggregate the intended group outcome once. Whichever relationship is intended
between Battletide and native self-vamp, it must be independent of iteration
order. Do not blindly replace the assignment without choosing that relationship.

**Verify:** all permutations of injured/full/capped/out-of-room allies, no
group, and earlier personal vamp success; confirm equal composition gives
equal self-healing.

## F07 — Ordinary Soulshield changes later shield reactions' damage basis

**Status:** P2, reproduced inconsistent composition.

**Evidence:** the non-Holyman Soulshield branch assigns
`dam = int(dam*soulshielddam)`, then the following elemental-shield family
uses the modified variable. Negative Shield and Holyman Soulshield instead
pass a scaled expression without changing that shared basis. With incoming
basis 100, the compiled float/truncation path gives Fireshield 64 alone, but
ordinary Soulshield 34 followed by Fireshield 22. The nominal factors are .35
and .65; the one-point differences reflect current float truncation.
[Soulshield and following shield family](../../../src/combat/fight.c#L5285),
[configured shares](../../../lib/duris.properties#L221).

**Gameplay:** adding ordinary Soulshield can reduce a coexisting elemental
shield's retaliation. The smaller variable also reaches later threshold
checks such as Acid Blood. Class/spec changes can therefore alter otherwise
identical shield combinations in a way their independent descriptions omit.

**Fix:** retain the original incoming basis and use a separate Soulshield
amount, as the neighboring branches already do. If chained reductions are
intended, apply/document them consistently across the alternatives instead.

**Verify:** no spiritual shield, ordinary/Holyman Soulshield, Negative Shield,
each elemental shield and later threshold effects, including terminal returns.

## F08 — Warring Zeal ignores its dice-size setting

**Status:** P2, reproduced configuration wiring defect.

**Evidence:** the post-melee proc reads `spell.warringzeal.dize.num` for both
the number and size of dice. The committed file supplies num 8 and size 5,
but production rolls 8d8. Changing only `.dize.size` does nothing. The fixture's
maximum was 64 rather than the configured 8d5 maximum 40; mean base payload is 36
rather than 24 before later damage stages.
[Proc](../../../src/combat/fight.c#L5720),
[two configuration keys](../../../lib/duris.properties#L969).

**Gameplay:** eligible hit-based holy procs are 50% stronger in mean base
damage than the two settings describe. Fast races and multi-hit builds can
benefit more often; staff tuning the size property sees no effect.

**Fix:** read `.dize.size` for the second argument. Preserve the established
key spelling for compatibility; a broader property rename is unnecessary.

**Verify:** independently change count and size, check min/mean/max dice,
and ensure the proc still passes through its existing holy-damage defenses.

## F09 — Boosting a dwarven Berserker skill above 100 loses its speed bonus

**Status:** P2, reproduced threshold defect; a particular obtainable boosting
item/build was not established in this review.

**Evidence:** the quality 3 Berserker branch and `berserk_combat_pulse()` require
both effective Berserk and Indomitable Rage ratings to equal 100 exactly.
Effective skills can include additive affects. The helper returns-2 at 100/100
and-1 when the ratings are 101/101. Merely increasing a mastered rating can
therefore select the inferior branch.
[Quality and pulse helper](../../../src/cmd/actoth.c#L550),
[application branch](../../../src/cmd/actoth.c#L725),
[effective skill additions](../../../src/core/utility.c#L5227).

**Gameplay:** Mountain/Duergar Berserkers can lose a combat-pulse benefit when
otherwise beneficial skill bonuses push either rating above mastery.

**Fix:** use an at-least-mastery condition consistently in the helper and
application branch, if 100 is the intended mastery threshold. Preserve the
other racial Berserk benefits and ordinary quality 2 behavior.

**Verify:**99/100/101 for each skill independently, both dwarf races and a
non-dwarf control; include an actual additive skill affect.

## F10 — A penetration marker can lend its shrug bypass to another caster

**Status:** P2, reproduced helper-level ownership leak; requires another
eligible check before the short marker is removed/consumed.

**Evidence:** successful penetration adds an unowned
`SKILL_SPELL_PENETRATION` affect to the victim. `resists_spell()` immediately
returns false for any caster while that marker exists. The fixture penetrated
with one caster, then a second caster with no penetration bypassed shrug
without rolling; removing the marker restored its ordinary shrug result.
The damage predicate also consumes the marker without checking the caster.
[Marker and bypass](../../../src/classes/innates.c#L5028),
[damage consumption](../../../src/combat/dam_mods.c#L757),
[short-affect scheduling](../../../src/magic/affects.c#L2081),
[event eligibility](../../../src/world/new_events.c#L260).

**Gameplay:** closely ordered status spells, procs or other checks can share
one caster's penetration success. Shrug-heavy races can lose a defense against
an unrelated attacker, and the marker's damage reduction can be consumed by
the wrong subsequent spell. Its short lifetime narrows the window but does
not establish ownership.

**Fix:** scope the bypass to the originating caster/effect resolution. Preserve
the reason repeated checks within one spell need a bypass, but do not expose
it as a target-wide permission for unrelated casts.

**Verify:** two casters with different penetration ratings, status-only first
spell, multiple checks inside one spell, nested procs, marker expiry and exact
once-only damage reduction.

## F11 — Fully negated physical hits still deal chip damage and spend skins

**Status:** P2, reproduced behavior contradicting Displacement's current
“deals nothing” facts; chip/charge policy should be made explicit.

**Evidence:** Earth Aura/Displacement can set intermediate damage to 0, but
execution proceeds through skin deduction/charge consumption and `MAX(1,dam)`.
Both fixture paths delivered 1 and reduced Stone Skin charges from 2 to 1.
Displacement's facts explicitly describe a chance that a melee hit deals
nothing. A ward's complete absorption instead exits early.
[Negation and skin ordering](../../../src/combat/fight.c#L5593),
[minimum and delivery](../../../src/combat/fight.c#L5704),
[Displacement facts](../../../src/classes/psionics.c#L2207).

**Gameplay:** an apparently avoided hit can still chip HP, consume finite
defense charges, wake or release damage-sensitive control, and qualify for
later hit-associated effects. Wight's native Stone Skin and fast attackers
make the charge interaction relevant to racial comparisons.

**Fix:** distinguish an actually negated hit from a positive hit reduced below
the damage floor. If the effect is full negation, finish that delivery before
skin use and HP damage while preserving required engagement messages. If chip
damage is intentional, correct facts and explicitly decide charge/proc behavior.

**Verify:** Earth Aura and Displacement, with/without each skin, Combat Mind,
NOREDUCE, low-HP targets and damage-sensitive control; blocked hits must follow
the chosen HP/charge/proc contract.

## F12 — Spell control and banishment can survive damage negation

**Status:** P2 contract/design review; ordering reproduced. This is separate
from F02's unequivocal terminal-result handling.

**Evidence:** Polar Vortex applies its paralysis before calling `spell_damage`;
shrug/ward/absorption in the damage pipeline cannot undo that already-applied
state. Word banishment is called even when damage returns nonterminal after
negation. The fixtures retained paralysis and invoked banishment under the
documented zero-HP/nonterminal result contract.
[Polar Vortex](../../../src/classes/ethermancer.c#L3416),
[word follow-up](../../../src/magic/magic.c#L19919),
[spell negation returns](../../../src/combat/fight.c#L4418).

**Gameplay:** a character may resist the damage yet remain paralyzed or be
banished. Thri-Kreen's extra cold-control route and the Gith races' word
weaknesses make this more than a generic damage discrepancy. High shrug does
not protect these effects as a reader of a whole-spell resistance message
might expect.

**Fix:** decide whether each secondary effect is independently admitted or
part of the resisted spell. For whole-spell resistance, resolve that gate once
before applying control. For intentionally separate effects, keep their own
saves and clearly describe the bypass. Do not reroll shrug repeatedly until
one check happens to pass.

**Verify:** shrug, ward, globe, aura absorption, deflection and normal damage;
check damage and each control/movement effect separately for the relevant races.

## F13 — Damage admission and follow-up contracts permit effects on refused hits

**Status:** P2, reproduced API ordering/response defect; no end-to-end player
command exploit is claimed for every caller.

**Evidence:** `raw_damage()` consumes a not-yet-checked ward before its
safe-room/`should_not_kill` refusal. A fixture using the actual prefix spent a
20-point guardian ward and then returned for the safe room. Outer spell and
physical delivery also have side effects before reaching those raw gates.
Separately, `melee_damage` treats nonterminal return as enough to run Warring
Zeal and shield reactions; a zero-HP/nonterminal adapter still triggered both.
[Raw admission ordering](../../../src/combat/fight.c#L6200),
[spell ward/early effects](../../../src/combat/fight.c#L4450),
[post-raw follow-ups](../../../src/combat/fight.c#L5710).

**Gameplay:** a disallowed damage request can consume protection or perform
other earlier effects even though HP loss is refused. Hit-triggered reactions
can also run when a later absorption prevented HP loss. That latter contact
policy may be intentional for some effects; it must not be confused with
permission to affect a protected target.

**Fix:** establish legality before irreversible combat effects, retaining
legitimate self/environmental exceptions. Distinguish terminal, prohibited,
absorbed and delivered outcomes where follow-ups need the distinction. Do not
globally require HP loss for every contact proc without reviewing its contract.

**Verify:** rejected safe/protected attacks preserve wards/appearance/state;
legal ward/Vines/Imprison absorption follows its chosen contact rules; nonlethal
zero-damage and ordinary delivery do not get conflated.

## F14 — Multiple ward providers over-count absorbed damage

**Status:** P3 conditional arithmetic defect. Ordinary guardian wards are
mutually exclusive, the old innate ward pool is retired, and no current
ordinary-player route to the tested combination was established.

**Evidence:** after earlier absorption, later branches subtract only remaining
demand from a provider but add a full-demand expression to `absorbed`. At
mitigation .80, a 30-point ward plus 20 pool points reports 100 incoming damage
absorbed, although 50 ward units cover only 62.5 before return rounding. A
synthetic two-affect case can make `absorbed` exceed demand and increase an
existing pool from 10 to 40. These execute the actual helper, but the fixtures
must not be mistaken for a demonstrated current build.
[Ward helper](../../../src/combat/fight.c#L494),
[guardian mutual exclusion](../../../src/magic/smagic.c#L297),
[retired base pool and recalculation](../../../src/magic/affects.c#L1039).

**Gameplay:** if multiple providers/persisted/custom state reach the helper,
characters can receive excess protection or even regain ward pool while hit.
The normal single-guardian, zero-pool path does not demonstrate this defect.

**Fix:** track remaining demand and actual consumed capacity consistently,
never allowing absorbed demand to exceed its limit or a hit to replenish a
provider. If multiple providers are no longer supported, remove/reject that
state explicitly instead of preserving broken dormant arithmetic.

**Verify:** one provider, depleted providers, effect-plus-pool, multiple effects,
exact exhaustion, zero capacity and supported mitigation bounds. Establish a
real source of combined state before treating this as a live balance exploit.

## F15 — Float rounding removes a point from some racial damroll caps

**Status:** P3, reproduced numeric boundary defect.

**Evidence:** cap calculation multiplies the loaded float by 50 and truncates.
For Troll/Centaur's factor 1.18, the binary float product is just below 59 and
stores 58, whereas the decimal setting implies 59. Other genuinely fractional
products, such as a 38.5 cap, raise a separate intentional rounding question.
[Cap assignment](../../../src/magic/affects.c#L929),
[factors](../../../lib/duris.properties#L267),
[Centaur factor](../../../lib/duris.properties#L279).

**Gameplay:** capped Troll/Centaur builds lose one stored damroll point relative
to the configured decimal boundary; at lower gear values there is no effect.
Subsequent damroll randomization/truncation determines whether a particular
hit changes. This is not a one-point loss on every final hit.

**Fix:** define the cap's decimal/near-integer rounding policy and calculate it
consistently. Correct near-integer precision loss without rounding every
deliberately fractional cap upward.

**Verify:** all 37 racial factors, exact-integer and half-integer products,
values just below/at/above the cap, and configurable nondefault cap values.

## F16 — Parry's supposed floor rolls twice and is intentionally retained today

**Status:** P3, reproduced implementation mismatch, explicitly allowlisted by
the current random-clamp test as behavior whose correction can change balance.

**Evidence:** both parry rolls use `MAX(5,number(...))`, where `MAX` is a
macro that can evaluate the random argument twice. A controlled sequence
produced defender 1/attacker 5 using four draws, despite the written floor 5.
The current `test_random_roll_clamps.py` includes both parry sites in its
allowlist; this is not an unnoticed omission to silently sweep into another fix.
[Parry rolls](../../../src/combat/fight.c#L10037),
[macro](../../../src/core/utils.h#L53),
[retained exceptions](../../../tests/async/test_random_roll_clamps.py#L8).

**Gameplay:** actual opposed-roll distributions differ from a single draw
clamped at 5, changing parry odds and the value of racial STR/DEX/WIS inputs.
The reference's simple max-floor equation needs this caveat.

**Fix:** document current behavior immediately. Compare old/new distributions
across representative scores, then deliberately adopt a single-evaluation
clamp if that is the desired rule, updating the allowlist and regression
expectations together.

**Verify:** deterministic draws showing the old extra evaluation, exact
success distributions at small/asymmetric/equal scores, and no hidden notching
or status changes in the comparison.

## F17 — One Sanctuary aura has zero, one, or two class-dependent reductions

**Status:** P2 design/contract review; class behavior reproduced, not declared
an automatically wrong balance choice.

**Evidence:** two independent raw predicates apply Sanctuary: one for Paladin
with group scaling and one for Cleric. A Warrior with the same flag gets
neither; a Paladin/Cleric can get both. With no group bonus, the isolated
factors are 1/.75/.75/.5625. The spell applies its aura to the caster without
that class check. The engine recognizes a Paladin/Cleric combination, and
`GET_CLASS` checks both primary and secondary class.
[Sanctuary predicates](../../../src/combat/dam_mods.c#L949),
[aura producer](../../../src/magic/magic.c#L16533),
[class membership](../../../src/core/utility.c#L5060),
[combination](../../../src/core/constant.c#L144).

**Gameplay:** an aura obtained outside its normal class can look protective
without this reduction, while a qualifying multiclass gets compounded benefit
from one aura. Native multiclass access makes this particularly relevant to
Human/Orc comparisons, subject to each race's legal class combinations.

**Fix:** choose whether the buff is universal, limited by class, or deliberately
enhanced by multiclassing. If one best applicable reduction is intended, select
it once. If current behavior is intended, expose it in spell/item facts and
refuse misleading unsupported activations where appropriate.

**Verify:** Paladin, Cleric, both, neither, group scaling, item-granted flags
and defaults toggled by the damage-call flags.

## F18 — Vamp priority can make a healing buff reduce undead sustain

**Status:** P2 design/contract review; non-monotonic healing reproduced.

**Evidence:** successful PC Touch healing sets `vamped`, preventing the later
native-undead route. In an otherwise identical 100-damage Touch-eligible
fixture, an undead Warrior healed 75 without the Touch bit but only 15 with
Vampiric Touch. Other classes have different shares; actual cap/suppression
and zero-heal returns can change which later route is reached.
[Touch priority](../../../src/combat/fight.c#L5898),
[native undead fallback](../../../src/combat/fight.c#L6097),
[configured shares](../../../lib/duris.properties#L112).

**Gameplay:** adding Vampiric Touch can reduce healing for an eligible undead
build. PC Vampire owns the bit natively, while weapon and unarmed/skill flags
can select different paths. Comparing advertised healing percentages without
priority and flags can therefore reverse the actual sustain comparison.

**Fix:** decide whether healing routes intentionally replace one another or
should select the strongest eligible personal result. If replacement is
intentional, describe it as a tradeoff; otherwise select the intended amount
before applying healing once. Keep group healing separate, as required by F06.

**Verify:** all configured class shares, native undead/non-undead, Touch versus
weapon/arrow flags, full and partial caps, suppression effects, Vampire Form
and Battle Ecstasy; never assume all vamp percentages add together.

## Findings already owned by earlier layers

These remain important when interpreting combat results. They are carried-forward
findings, not new discoveries; a source/issue status check should accompany
implementation work.

| Existing finding | Gameplay consequence here | Recommendation |
|---|---|---|
| [Innates F04: Eyeless subject](race-innates-issues.md#f04--defense-eligibility-reads-the-attackers-eyeless-innate) | The attacker's innate can admit the defender's visibility-gated defense chain. | Correct the subject and test visibility from both participants' perspectives. |
| [Innates F08: Giant Avoidance](race-innates-issues.md#f08--giant-avoidance-can-make-an-intermediate-dodge-score-worse) | Multiplying an already-negative score can worsen the intended dwarf bonus. | Define a nonnegative bonus application and test around zero/floors. |
| [Innates F03: Troll burn](race-innates-issues.md#f03--repeated-fire-does-not-actually-extend-troll-burn-expiry) | Repeated fire can fail to maintain the intended regeneration suppression. | Reschedule the owning expiry rather than only changing a duration field. |
| [Innates F22: Rrakkma AC](race-innates-issues.md#f22--rrakkmas-ac-scaling-has-no-shrug-style-holder-cap) | AC and shrug group scaling have different limits. | Decide caps separately; do not assume the shrug limit applies to armor. |
| [Innates F23: Fury](race-innates-issues.md#f23--warcallers-fury-scales-from-the-victims-group-and-reaches-spells) | Orog's raw-stage scaling follows the target's group and can affect spells. | Preserve or deliberately change the intended subject and damage scope. |
| [Innates F26: regeneration representation](race-innates-issues.md#f26--regenerations-combat-benefit-depends-on-affect-representation) | Passive and affect-backed regeneration can yield different in-combat recovery. | Establish one explicit recovery policy and test both representations. |
| [Innates F15: race identity](race-innates-issues.md#f15--shape-ownership-and-innate-payload-use-different-race-identities) | A form can grant ownership while native-race checks choose a different payload. | Specify ownership versus mechanics race per effect; avoid a blanket identity rewrite. |
| [Size F03: Trip window](race-size-issues.md#f03--trip-has-an-impossible-body-size-window) | Horse/Spider Body targets have contradictory admission windows. | Reconcile command/body size rules and test each boundary. |
| [Size F13: crowding](race-size-issues.md#f13--pvp-crowding-omits-the-candidates-size-from-its-budget) | Joining order and other attackers' sizes can change admission. | Decide whether the incoming attacker belongs in the budget, then align entry and hit checks. |
| [Tempo F02/F03: attack shares](race-tempo-issues.md#f02--halving-attacks-duplicates-early-weapon-slots-instead-of-selecting-a-subset) | Suppression can repeat early slots; unsupported shares can divide by zero. | Fix slot selection and validate supported multipliers before judging four-hand or proc output. |
| [Tempo F04: lethal arrow](race-tempo-issues.md#f04--a-lethal-arrow-is-omitted-from-the-volley-recovery-calculation) | A killing arrow can shorten the volley recovery paid. | Count the arrow when launched, including terminal delivery. |
| [Tempo F05: pulse reversal](race-tempo-issues.md#f05--enough-pulse-gear-can-make-a-slower-racialclass-base-faster) | Sufficient modifiers can reverse the nominal racial speed ordering. | Establish attainable ranges and intended curve before retuning racial damage. |
| [Stats F09: stat-save floor](race-stats-issues.md#f09--statsave-contradicts-its-stated-failure-floor) | The strict 1..21 comparison caps ordinary stat saves at 19/21. | Reconcile the intended floor and descriptions; keep Quick Thinker separate. |
| [Stats F07/F08: high-stat curves](race-stats-issues.md#f07--more-con-can-lower-maximum-hp-above-the-curves-peak) | The earlier stat audit identifies high-CON/AGI regions where increasing a stat can worsen HP or armor, subject to reaching those ranges. | Recheck attainable builds and both curves before assuming all stat buffs improve durability; keep this separate from damage multipliers. |

## Reviewed observations that do not establish another current bug

- **Monk superhit's 225/floor ordering:** a hypothetical MonkDamage above 225
  can bypass the cap and introduce a discontinuity. At ordinary level 56 and
  martial arts 100, however, the real bare-hand maximum is 8d8+9=73 before a
  non-increasing weight adjustment. Exceeding 225 at maximum dice would need
  effective martial arts at least 1782 or another nonstandard route; no such
  ordinary build was established. Do not report the hypothetical 300-damage
  fixture as proof of a live player cap exploit.
  [MonkDamage](../../../src/classes/new_skills.c#L650),
  [superhit](../../../src/combat/fight.c#L11359).
- **Racial spell-type factors add within one predicate.** They are neutral
  for all 37 PC races in current settings, and the existing test explicitly
  preserves that combination rule. Changing it to multiplication is a tuning
  decision, not an automatic off-by-one fix.
  [Predicate](../../../src/combat/dam_mods.c#L767),
  [contract test](../../../tests/async/test_racial_spell_damage.py).
- **Coupled flags are real contracts:** NOSHRUG also bypasses WIS reduction
  and Spell Absorb; NODEFLECT skips several item/class defenses; spell/raw
  defaults use XOR where physical delivery uses OR. Keep those meanings
  explicit and test callers before separating or renaming flags.
  [Flags](../../../src/combat/damage.h#L119).
- **Raw quartering, damage-profile caps, WIS breakpoints, skin precedence,
  hit-packet thresholds, independent body immunities and the 99% ordinary hit
  boundary** can all create sharp balance differences. Their asymmetry alone
  does not establish a coding error. The reference documents their actual
  routes and gives controlled comparisons.
- **Ordinary undead identity:** `IS_UNDEAD` already includes the eight native
  PC undead races through `OLD_RACE_PUNDEAD`. For these native PCs, the two
  undead macros do not establish an extra immunity mismatch. The reference
  wording was corrected to avoid implying one.
  [Legacy list included by the macro](../../../src/core/utils.h#L1126).
- **Dummy identity:** a training dummy writes its selected race into
  `player.race`. Tutorial NPC appearance/mechanics overrides are a different
  facility. Do not infer missing dummy defenses merely because a consumer
  reads `GET_RACE`; dummy differences such as NPC handling and early damage
  recording still limit full-build conclusions.
  [Dummy profile](../../../src/combat/training_dummy.c#L231),
  [tutorial identity](../../../src/specs/specs.ailvio.c#L32).

## Already corrected or intentionally excluded from rediscovery

The current source and focused tests include Leap ownership/unlock checks,
PC Vampire's separate shrug key, correct racial spell-type indexing, and
the cleaned shield-block code. The earlier wrong-subject Sanguinis Ignis
Power read now uses the defending Dragoon. Recent random-clamp work corrected
Hellfire and named-weapon vamp rolls, while deliberately retaining the parry
sites discussed in F16. These should not be filed again as still-active
versions of their older defects.
[Leap checks](../../../tests/async/test_innate_action_dispositions.py),
[shrug key](../../../tests/async/test_racial_shrug.py),
[type indexing](../../../tests/async/test_racial_spell_damage.py),
[Sanguinis check](../../../tests/async/test_low_combat_dispositions.py),
[random clamp policy](../../../tests/async/test_random_roll_clamps.py).

## Verification and limits

The audit covered all twelve sections of the combat-resolution reference,
its three 37-race tables and twelve worked comparisons, then followed the
suspect branches in current source. No GitHub issues were filed and no
gameplay, configuration, player data or deployment state was changed.

Ignored review artifacts under
`bin/tests/race-combat-resolution-issues-review/` contain three executable
fixture groups:

- `runtime_review.py`: ward accounting/admission, pressure-point ownership,
  parry double evaluation, dwarven mastery thresholds, feeding, Battletide
  ordering, Touch priority, Orc scaling and penetration ownership.
- `pipeline_review.py`: negation/skin use, Sanctuary predicates, Warring Zeal
  configuration, shield-basis mutation, nonterminal-result follow-ups and
  float cap boundaries.
- `outcome_review.py`: Polar Vortex ordering, word terminal/nonterminal
  follow-ups and discarded nested Alliance outcomes.

They compile current production functions/predicates or relevant source
blocks with real engine types and AddressSanitizer/UndefinedBehaviorSanitizer.
Scheduler, death, delivery and healing adapters isolate the stated contracts;
they do not prove actual object deallocation, obtainable equipment, every
upstream command path or a live PvP exploit. Synthetic ward stacking and
extreme hypothetical Monk damage are specifically not ordinary-build proof.

The seven focused suites passed: racial shrug, racial spell damage, Holy
Sacrifice/vamp caps, innate actions/Leap, low combat dispositions, random-roll
clamp policy, and damage-result lifetime. Their logs are recorded alongside
the fixtures. The random-clamp test explicitly retains the F16 behavior;
passing it does not prove that parry evaluates its roll once.

Local-link/anchor checks, finding coverage, source freshness and whitespace
checks are also recorded with the review artifacts.
Each finding above includes the additional regression that should accompany
its eventual fix. No server build is needed for this documentation-only change.
