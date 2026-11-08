# Race stats: potential bugs, gameplay impact, and recommended fixes

Reviewed 2026-11-08 against checkout
`00dc3ddd2ef8bbf6503409cd67e510341d4f9155`.
Companion to [race-stats.md](race-stats.md), whose source snapshot was
`2c04736f56ce35f2e0bf648287dcca6ea72bad29`. This review rechecked suspicious
paths against current source, including changes since that snapshot.

This document contains **26 findings**: implementation inconsistencies, likely
bugs, edge cases, and explicit design/documentation questions. They are not 26
proven unintended gameplay defects. Each entry gives evidence, conditions,
gameplay impact, a recommended disposition, and useful regression cases.
A resolved finding is recorded separately. No gameplay code, balance settings,
production state, or player data was changed or inspected through a live session.

## Evidence and priorities

- **Reproduced:** extracted production functions or predicates executed locally
  under AddressSanitizer and UndefinedBehaviorSanitizer. Fixture results prove
  the calculation, not a full MUD journey or an obtainable item/build.
- **Source verified:** executable conditions or conflicting implementations are
  present; the full encounter was not exercised.
- **Design decision:** behavior is verified, but intent cannot be established
  from code. Recommendations do not authorize a silent rebalance.
- **Dormant API:** no active caller of the defective interface was found.

**P1** applies to the conditional knockout-without-expiry defect in F25.
**P2** means a gameplay/state consistency fix worth prioritizing when used.
**P3** means a narrower edge case, documentation correction, dormant interface,
or balance decision. Priorities do not claim production frequency; no live
incident was established by this review.

Recommended starting order:

1. Prevent boulder knockout without expiry (F25), then address HP equipment
   eligibility (F03–F04), wrong-subject stats (F12/F26), and reversed save
   modifiers (F10–F11), with focused regressions.
2. Shop arithmetic/quotes (F01–F02), Luck checks, and beast admission (F13–F15).
3. Decide the racial override contract (F05–F06) and high-stat HP/armor behavior
   (F07–F08) before tuning racial factors.
4. Address remaining caps, apply units, displays, and documentation without
   automatically changing intentional thresholds.

## F01 — Ordinary shop guards erase Charisma pricing

**Status:** reproduced arithmetic; source verified in all four routes.
**Priority:** P2. **Recommendation:** fix.

Buy, sell, value, and list look up
`cha_app[STAT_INDEX(max(100,currentCHA))]`. Every reachable value is positive.
Buy/list reduce the shop's selling factor, then a guard replaces that improvement
with `sell_percent + 0.01`. Sell/value increase the buying factor, then replace
it with `buy_percent - 0.01`. The CHA-100 floor also hides low-CHA penalties.
Same-race/different-race adjustments are swallowed by the guards.

**Gameplay:** ordinary prices do not reward higher racial CHA. With selling
factor 1.50 and buying factor 0.50, CHA 25, 100, 200, and 511 all produce **1.51
for buying and 0.49 for selling**, before Barter, epic, condition, trophy, and
other shop rules. Investment in CHA cannot deliver this expected discount.

**Fix:** agree on the intended discount/premium range and bound it in the
favorable direction, retaining positive prices and a shop spread. Decide whether
CHA below 100 should be floored. Keep quote/list and transaction calculations
consistent, preserving intentional Barter presentation differences.

**Verify:** low/normal/high CHA, same/different keeper race, all four commands,
condition/trophy/epic adjustments, and no profitable buy/sell loop.
[Buy](../../../src/economy/shop.c#L1103),
[sell](../../../src/economy/shop.c#L1310),
[value](../../../src/economy/shop.c#L1473),
[list](../../../src/economy/shop.c#L1618),
[CHA table](../../../src/core/constant.c#L1104).

## F02 — Barter lowers a selling quote and is absent from the sale

**Status:** source verified. **Priority:** P2. **Recommendation:** fix.

`shopping_value` copies the buy-side Barter adjustment: success on
`CHA > number(0,125)` subtracts 0.25 from the factor the keeper would pay;
failure adds 0.10. `shopping_sell` has no corresponding Barter block.

**Gameplay:** higher CHA makes a worse quote more likely for a Barter character,
and the eventual sale uses another factor. With F01's 0.49 selling factor,
the quote can use **0.24 on success or 0.59 on failure**, while the transaction
starts at 0.49. Subtracting 0.25 benefits the player when buying, not selling.

**Fix:** make `value` describe the sale. My default is to remove the stray
valuation adjustment to match selling. If Barter should benefit sales too, add
an agreed beneficial adjustment to both paths and make quotations stable.

**Verify:** Barter at low/high CHA, forced success/failure, quote versus sale,
with condition and trophy adjustments held equal.
[Value](../../../src/economy/shop.c#L1483),
[sale](../../../src/economy/shop.c#L1310),
[purchase](../../../src/economy/shop.c#L1113).

## F03 — HP racial CON scans equipment whose affects are inactive

**Status:** reproduced HP calculation; source-verified eligibility mismatch.
**Priority:** P2. **Recommendation:** fix.

Normal affect aggregation skips ordinary belt-2/3 attachments, weapons merely
held in HOLD, and inappropriate armor held in hand/weapon slots. HP's separate
CON-race scan considers every occupied slot without those checks.

**Gameplay:** an item can leave effective CON unchanged yet raise the racial
factor used for base-HP scaling and the quadratic term. A level-56 fixture with
base/precalculated HP 100, class multiplier 1, current CON 100, and no other HP
bonuses changed **523 → 1,463 HP** when an Ogre CON-race apply occupied an ignored
ordinary belt-2 slot. CON stayed 100. This is an accounting counterexample, not
an obtainable-item claim.

**Fix:** apply normal equipment eligibility to HP's factor scan, then apply the
chosen native-versus-override policy in F05. Make intentional exceptions explicit.

**Verify:** all slots, ordinary/artifact belt attachments, held weapons/armor,
valid body gear, invalid race IDs, removal/recalculation, and missing-HP
preservation. Check authored item availability before estimating live exposure.
[Normal scan](../../../src/magic/affects.c#L1720),
[HP scan](../../../src/magic/affects.c#L427),
[recalculation](../../../src/magic/affects.c#L1804).

## F04 — Caster MAX-CON bonus uses another equipment policy

**Status:** source verified; isolated HP slot behavior reproduced.
**Priority:** P2. **Recommendation:** reconcile the rules.

The extra caster HP sum for `APPLY_CON_MAX` excludes back and belt-2/3
unconditionally. Normal aggregation accepts back affects and artifact belt-2/3.
Conversely, the caster scan lacks normal held-item eligibility checks.

**Gameplay:** eligible MAX CON can raise displayed CON without contributing this
special bonus, while an ineligible held item can contribute the bonus without
raising CON. This is separate from ordinary CON-derived HP; the item can still
have that ordinary HP value.

**Fix:** use normal eligibility unless these are intentional caster-specific
exceptions. If intentional, document them consistently: the comment that
backpacks "don't give stats" does not describe the normal aggregator.

**Verify:** caster/noncaster and multiclass gates; back/body/HOLD and
ordinary/artifact belt slots; special bonus separately from effective CON.
Preserve the committed 1.0 multiplier unless deliberately rebalancing.
[Special sum](../../../src/magic/affects.c#L471),
[normal scan](../../../src/magic/affects.c#L1720),
[setting](../../../lib/duris.properties#L986).

## F05 — Stat replacement has conflicting native-factor rules

**Status:** downgrade reproduced; source-verified inconsistency.
**Priority:** P2, requiring a design decision.
**Recommendation:** define one contract, then align calculations and displays.

The strongest override wins without comparing it with the native factor; the
first override can reduce a stat. HP's CON scan and numeric attributes display
instead start with the native factor and only increase it. HP also scans only
equipment; ordinary stats accept applying character affects too.

**Gameplay:** base-100 Ogre STR falls **230 → 85** under a Gnome STR override.
A weaker CON override can lower displayed CON while HP retains native Ogre
scaling. A character-affect CON override can change effective CON without
selecting the same HP factor. These representations disagree even if some
replacement penalties are meant to exist.

**Fix:** I recommend upgrade-over-native semantics for beneficial race-stat
equipment if that matches authored intent. If replacement penalties are
intentional, preserve them and make HP/display use the selected replacement.
Audit affected data first: adding `max(native, …)` could otherwise erase curses.
Keep original Illithid's special HP formula explicit.

**Verify:** stronger/weaker/equal overrides on all ten attributes; several
overrides in either order; equipment versus character affects; removal,
recalculation, display, and HP.
[Selection](../../../src/magic/affects.c#L1281),
[effective factors](../../../src/magic/affects.c#L833),
[HP](../../../src/magic/affects.c#L427),
[display](../../../src/cmd/actinf.c#L5367).

## F06 — Excess-stat benefits retain native baselines after replacement

**Status:** source verified; design decision. **Priority:** P3.
**Recommendation:** decide and document the baseline.

Excess-DEX hitroll, excess-AGI armor, and spell-recovery formulas compare the
effective stat to the native factor, although a replacement factor may have
produced that effective stat.

**Gameplay:** a stronger factor can both raise the attribute and count as excess
credit. At the same INT 130, two book casters have tick factor **49 with native
INT factor 100 versus 19 with factor 130**, before other modifiers. Similar
differences affect hitroll/armor. This could be a deliberate racial gearing rule.

**Fix:** retain native baselines if intentional and explain replacement effects.
Otherwise use the selected factor consistently. Do not switch to a universal
100 as cleanup; that would change ordinary racial balance too.

**Verify:** equal final stats reached naturally, through MAX gear, and through
replacement; Human +5; override removal.
[AGI](../../../src/magic/affects.c#L921),
[DEX](../../../src/magic/affects.c#L981),
[ordinary recovery](../../../src/classes/memorize.c#L801),
[undead/tupor recovery](../../../src/classes/memorize.c#L638).

## F07 — More CON can lower maximum HP above the curve's peak

**Status:** reproduced. **Priority:** P2, conditional on high CON.
**Recommendation:** make the CON contribution nondecreasing.

The ordinary HP term `q(C)=level*(-14*C*C/152100 + 28*C/390 - 4)` peaks at CON
390, while effective CON can reach 511. The internal 780 cap prevents a later
collapse, not the decline immediately after 390.

**Gameplay:** a level-56 Gnome fixture, class multiplier 1, base/precalculated HP
100, and no other HP bonuses falls **893 → 818 HP** as CON rises **390 → 511**.
Caster MAX-CON gear has an independent bonus that can offset some of this;
epic/temporary CON need not. Missing-HP preservation also reduces current HP
when the maximum falls. Original Illithid uses a different formula.

**Fix:** plateau this HP contribution at 390, with an explicit balance decision
for further growth. Test the whole formula; do not clamp CON for saves or other
consumers, or silently replace the separate racial HP term.

**Verify:** CON 389/390/391/450/511; racial/class multipliers; spell/epic/item
CON; caster gear bonus; original/Planetbound Illithid; current HP preservation.
Establish obtainable totals before estimating frequency.
[Curve](../../../src/magic/affects.c#L449),
[effective cap](../../../src/magic/affects.c#L620),
[missing HP](../../../src/magic/affects.c#L1800).

## F08 — High AGI can worsen final armor with the configured multiplier

**Status:** reproduced final arithmetic with the committed setting.
**Priority:** P2, conditional on high AGI.
**Recommendation:** remove negative returns from the complete contribution.

The AGI-defense component worsens after roughly 275. Stored AC separately
subtracts `max(0,AGI-nativeFactor)`, which would offset this over the PC range
if unscaled. But final AC first multiplies negative stored PC AC by **0.5**,
then adds the AGI-defense component unscaled.

**Gameplay:** native AGI factor 100, pre-AGI stored armor -100, burden 75, and
other terms zero gives **AC -256 at AGI 410, but -243 at AGI 511**: worse armor.
Turning points depend on truncation, armor, settings, and the final clamp.
Dodge/control avoidance may still improve; that does not remove the AC penalty.

**Fix:** review the combined result under the actual negative-AC multiplier.
Choose a plateau or monotonic continuation for the intended useful range.
Clamping the isolated curve at 275 would also remove existing useful combined
gains above 275, so do not infer the desired fix from that component alone.

**Verify:** full apply-to-final-AC path; all 37 native PC AGI factors and effective
AGI 1..511; positive/negative armor, burden, monk modifiers, multiplier, and
-750/100 bounds. Testing without the 0.5 multiplier is insufficient.
[Stored subtraction](../../../src/magic/affects.c#L921),
[curve](../../../src/world/handler.c#L5320),
[final order](../../../src/combat/fight.c#L6752),
[setting](../../../lib/duris.properties#L2702).

## F09 — StatSave contradicts its stated failure floor

**Status:** reproduced exact roll enumeration. **Priority:** P2 for an odds
change; P3 for a comment correction. **Recommendation:** settle intended odds.

`number(1,21) < clamp(save_num,1,20)` fails on both 20 and 21 at the cap:
success is **19/21**, not the comment's 20/21. The score-1 floor gives zero
success; neutral index 16 gives 15/21.

**Gameplay:** capped ordinary stat defenses fail 9.52% instead of 4.76%. This
affects psionics, control/movement magic, and physical/NPC callers. Quick
Thinking can additionally pass certain INT/POW saves, so 19/21 is not every
character's final cap.

**Fix:** if the comment is authoritative, `<=` implements one failure at the
cap and one success at the floor. It also raises uncapped saves by 1/21;
review callers before applying it globally. If current odds are intentional,
correct the comment and lock down those odds instead.

**Verify:** all 21 rolls at scores 1/16/20; capped modifiers; Quick Thinking;
representative offensive and defensive consumers.
[Save](../../../src/core/utility.c#L3247),
[caller](../../../src/classes/psionics.c#L386).

## F10 — Innate blast gets easier to resist as its caster gains levels

**Status:** modifier reproduced; save use source verified. **Priority:** P2
for users of this innate. **Recommendation:** fix the sign.

The defender's POW StatSave gets `max(-3,(casterLevel-targetLevel)/3)`.
Positive StatSave modifiers help the defender, reversing the level advantage
used by other psionic attacks.

**Gameplay:** against target level 50, caster level **50 → 56** changes modifier
**0 → +2**, improving the ordinary save by up to 2/21. A lower-level caster can
instead make paralysis harder to resist. Original Illithid receives the innate;
it is a restricted race. The random paralysis gate and immunities still apply.

**Fix:** reverse to defender-minus-caster level, retaining the intended bound
after review. Do not change the opposite-sign NewSaves API to repair this caller.

**Verify:** equal and +/-3/6/large level gaps, fixed POW/gate roll, Quick
Thinking, and immunity. Raising caster level should not help the target save.
[Blast](../../../src/classes/psionics.c#L4062),
[comparison](../../../src/classes/psionics.c#L1539),
[grant](../../../src/classes/innates.c#L696).

## F11 — Spinal corruption can reward the target for caster POW

**Status:** modifier reproduced; source verified. **Priority:** P2.
**Recommendation:** replace the sign-changing product.

The first save modifier is `min(1,casterLevel-targetLevel) * POW_DIFF(caster,target)`.
POW_DIFF is target-minus-caster power index. Equal levels erase the entire power
difference; lower caster level reverses its sign.

**Gameplay:** caster level 49, target level 50, and target POW 100 gives modifier
**-4 at caster POW 70, but +9 at POW 200**. Ordinary first-save success rises
**11/21 → 19/21**. Raising caster POW is harmful here. A later save uses normal
POW_DIFF, so the stages disagree.

**Fix:** keep power difference's sign consistent and combine any level adjustment
separately. Do not just swap `min` for `max`, which invents another multiplier.

**Verify:** lower/equal/higher caster level crossed with lower/equal/higher POW,
both stages independently, caps, and Quick Thinking. Stronger caster POW must
not improve the first defender save.
[Both saves](../../../src/classes/psionics.c#L1943),
[POW_DIFF](../../../src/core/utils.h#L1009).

## F12 — Sanguinis ignis reads the attacker's POW for a Dragoon reaction

**Status:** threshold reproduced; source verified. **Priority:** P2, conditional
on existing/override-created Dragoons. **Recommendation:** fix the subject.

The mounted Dragoon opponent's activation combines its shaman spell knowledge
with `GET_C_POW(ch)/20`, reading the other combatant. The surrounding spell,
mount, posture, cooldown, and affect application all belong to `opponent`.

**Gameplay:** Dragoon skill 100 and POW fixed at 200 gives reaction threshold
**15 → 21 out of 100** as attacker POW rises 80 → 200. The Dragoon's own POW
does not supply this term, misattributing racial POW and MAX-POW benefits.

**Fix:** read `GET_C_POW(opponent)` unless explicit intent is to sense more
powerful enemies. If intentional, describe the enemy-dependent term that way.

**Verify:** asymmetric POW, swapped roles, mounted state, spell/cooldown gates,
and blind/stunned/prone exclusions. Dragoon is disabled for ordinary new
creation, but the spell remains registered; this is conditional, not dead code.
[Reaction](../../../src/combat/fight.c#L11157),
[registration](../../../src/classes/skills.c#L5027),
[policy](../../../lib/creation_availability.cfg#L43).

## F13 — Barbarian restoration gets rarer with higher Luck

**Status:** exact predicate enumeration reproduced. **Priority:** P2 if this
content is used. **Recommendation:** fix the direction after confirming intent.

After the Barbarian lightning and 1-in-20 gates, restoration requires
`Luck < number(0,500)`: conditional success is `(500-Luck)/501` at Luck 0..500,
then zero. The comment instead estimates a Luck/500-style benefit and omits the
outer lightning gate from its rough chance.

**Gameplay:** Luck 90 passes **410/501**; Luck 200 passes **300/501**; Luck 500/511
never passes. More Luck reduces this heal. Full odds also include the outer
1-in-25 lightning and 1-in-20 restoration gates; these are not per-swing
restoration fractions.

**Fix:** if Luck should help, use an agreed increasing predicate and accurately
describe the nested probability. If inverse Luck is intentional, document that
tradeoff. Preserve other gates.

**Verify:** all 0..500 rolls at low/normal/high Luck, forced outer gates, and
actual item/procedure assignment and availability. This is a content-specific
proc, not all Barbarians' normal healing.
[Predicate](../../../src/specs/specs.underworld.c#L2935).

## F14 — Roundkick uses a tenfold smaller actor Luck range

**Status:** exact roll enumeration reproduced. **Priority:** P2 for review.
**Recommendation:** make the asymmetry intentional or correct it.

Actor +5% score uses `Luck/10 > number(0,10)`; target -5% uses the same Luck/10
against **0..100**. Shared takedown processing adds its own adjustments too.

**Gameplay:** at Luck 100, the actor's gate is **10/11 (90.91%)**, versus the
target's **10/101 (9.90%)**. Actor Luck 110 makes its gate certain. High-Luck
races quickly lose marginal value in this actor term while defensive Luck
remains far from certain. These are score multipliers, not direct 90-point
changes to the chance to land roundkick.

**Fix:** my default is 0..100 for the actor, matching the paired target test and
surrounding scale. Confirm intended balance and inspect shared takedown Luck
before changing it, to avoid accidental double counting.

**Verify:** paired forced rolls, Luck 90/100/110/130, score truncation, the shared
helper, and final success limits.
[Checks](../../../src/cmd/actoff.c#L5943),
[helper](../../../src/cmd/actoff.c#L588).

## F15 — Beast admission permits one follower above the CHA limit

**Status:** boundary reproduced; summon path source verified. **Priority:** P2.
**Recommendation:** correct the pre-summon comparison if this is a total limit.

The guard counts matching existing beasts, adds level to animalist CHA, and
rejects only at `count > max(1,CHA/30)`. It runs before adding the next follower.

**Gameplay:** CHA 100 nominally allows three but permits the fourth; CHA 120
permits the fifth. The minimum-one branch permits two. This shifts the gearing
breakpoints for another attacking/control unit. Only the counted vnum families
and ordinary summon prerequisites apply. The common function checks
`max_summon` for positivity but does not use it as a second follower-count cap.

**Fix:** reject at `count >= limit` if the value means total allowed. If the
extra beast is intended, express and document the actual total instead.

**Verify:** limit-1/limit/limit+1, CHA 29/30/59/60/89/90/119/120, animalist level,
regular/greater beasts, unmatched pets, and incompatible-pet guards.
[Count](../../../src/magic/smagic.c#L4297),
[pre-creation call](../../../src/magic/smagic.c#L4391),
[addition](../../../src/magic/smagic.c#L4496).

## F16 — Effective-derived applies receive racial scaling again

**Status:** Feeblemind example reproduced; herb producers source verified.
**Priority:** P2 if advertised fractions are intended; otherwise a balance
decision. **Recommendation:** settle producer units.

Feeblemind calculates loss from effective INT/WIS, then writes it as an unscaled
regular apply. Black Kush and Gootwiet also derive some modifiers from effective
stats before racial scaling again. Effects intentionally using base fractions
have a different contract.

**Gameplay:** base-100 Gnome INT 130, caster level 50, and Feeblemind roll +5
reports loss **58**; applying -58 unscaled gives INT **55**, an effective loss
of **75**. Lower factors can attenuate losses. Regular positive herb applies
can also disappear at the cap: a capped smoker may take physical penalties with
no mental-stat increase. Existing regular gear can mask some debuffs too.
The displayed fraction does not imply a uniform racial outcome.

**Fix:** for an effective-stat fraction, convert to unscaled units using the
selected factor and defined rounding/caps. For a base/unscaled modifier,
calculate and describe that value. Do not broadly turn regular buffs into MAX
buffs; that is a separate balance change. Preserve intentional scaling of fixed
and base-derived applies.

**Verify:** low/high/native/replacement factors, base 80/100, regular/MAX gear,
positive caps, penalties, final displayed stats, and herb tradeoffs.
[Loss](../../../src/magic/magic.c#L20264),
[apply](../../../src/magic/magic.c#L20365),
[Black Kush](../../../src/core/smoke.c#L794),
[Gootwiet](../../../src/core/smoke.c#L921),
[scaling](../../../src/magic/affects.c#L833).

## F17 — Feeblemind's loss can become a positive stat apply

**Status:** helper reproduced; application source verified. **Priority:** P3,
conditional on an already very low stat. **Recommendation:** floor losses at zero.

`effectiveStat/3 + casterLevel/5 + random(-15,5)` is not bounded before negation
into INT/WIS applies. Effective stat 1, caster level 50, and roll -15 produces
loss **-5**, hence a **+5 regular apply**.

**Gameplay:** a sufficiently debuffed target can receive a stat increase from
one component of successful Feeblemind alongside its other harmful effects.
Normal undepleted high-level PC stats are not this example. The spell rejects
an existing Feeblemind; other penalties would have to create the low input.
That full encounter was not exercised.

**Fix:** floor loss at zero separately from F16's unit decision. A minimum
positive loss is another design choice; zero is the smaller change. Keep the
two stat rolls independent.

**Verify:** stats 1/10/30/100, low/high caster levels, both random extremes,
other debuffs, and no sign reversal.
[Helper](../../../src/magic/magic.c#L20264),
[application](../../../src/magic/magic.c#L20365).

## F18 — Gambler's Luck bypasses the effective-stat cap

**Status:** cap sequence reproduced. **Priority:** P3; design decision.
**Recommendation:** specify whether the innate is an exception.

Luck is bounded to 1..511, then Gambler's Luck adds 10 without another bound.
A level-26+ Halfling can reach **521**. This requires enough MAX Luck to reach
the pre-innate cap; obtainable totals were not established.

**Gameplay:** direct Luck/loot consumers that have not saturated can benefit
beyond the nominal ceiling. This does not establish overflow or an out-of-bounds
table read: storage is wide enough and STAT_INDEX returns its last bucket.

**Fix:** clamp after the innate if 511 is global. Otherwise document the
exception and test direct consumers through 521. Preserve the normal level-26
bonus.

**Verify:** pre-innate 500/501/510/511, grant/removal/recalculation, direct rolls,
and index safety.
[Bound](../../../src/magic/affects.c#L893),
[addition](../../../src/magic/affects.c#L1032),
[grant](../../../src/classes/innates.c#L824).

## F19 — DEX extra attacks accept bare hands despite the comment

**Status:** source verified. **Priority:** P3; behavior/comment conflict.
**Recommendation:** confirm unarmed eligibility.

The active block says bare hands are excluded, but both slot checks accept a
null weapon as weight zero. At DEX 125 the primary can add an attack; at DEX 150
both empty slots can. They use normal attack dispatch. The separate two-handed
weapon substitution is intentional behavior, not evidence of this discrepancy.

**Gameplay:** high-DEX unarmed builds can gain attacks without a weapon-weight
tradeoff, including a second empty-hand roll. That may be desirable, but balance
comparisons assuming only light weapons qualify are wrong.

**Fix:** my default is to preserve behavior and correct the comment unless an
explicit balance requirement excludes bare hands. If excluding them, require
the appropriate weapon while preserving two-handed substitution. Do not revive
the commented old ladder.

**Verify:** empty hands, monk/nonmonk, light/heavy weapons, two-handed primary,
DEX 124/125/149/150, and added-attack dispatch.
[Block](../../../src/combat/fight.c#L10703).

## F20 — The attributes display reconstructs “Base” with another factor policy

**Status:** source verified. **Priority:** P3. **Recommendation:** correct its
label and value source.

The numeric attributes display labels a value Base but reconstructs it from
current stats divided
by an equipment-derived factor. That scan has separate slot exclusions, ignores
character-affect overrides, and only improves on native factors. It does not
read saved base stats.

**Gameplay:** a base-100 Human with +5 displays approximately **105** there.
An Ogre under the Gnome STR replacement has current STR 85, but the display
retains factor 230 and reconstructs **37**, despite saved base STR 100.
This misleads permanent-stat investment and gear debugging; it does not itself
change combat stats.

**Fix:** show `base_stats` if calling the value Base. If current unscaled potency
is wanted, name it accordingly and use gameplay's selected factor/aggregation,
explaining post-scaling innates separately. Avoid another independent scan.

**Verify:** normal races, Human +5, Halfling Luck, regular/MAX gear, stronger and
weaker replacements, character affects, and inactive equipment.
[Display scan](../../../src/cmd/actinf.c#L5359),
[printed values](../../../src/cmd/actinf.c#L5447),
[storage](../../../src/core/structs.h#L1071).

## F21 — Racewar modifier API discards its maximum argument

**Status:** source verified; dormant API. **Priority:** P3.
**Recommendation:** clarify the contract before reuse.

The setter discards `max_stat`; the application copies the regular value to
both current and maximum modifiers. Unsupported stats also return success
because there is no rejecting default case.

**Gameplay if used:** +5 regular/+0 MAX becomes +5 to both, growing capped stats;
maximum-only requests are lost. Unsupported requests look successful. No setter
caller was found in current source, and startup resets the vectors. This is not
evidence of an active racewar imbalance. Human's explicit current-and-maximum
bonus is a separate path.

**Fix:** remove the unused maximum argument and document a single MAX-style
modifier, or store separate values with intended fallthrough semantics. Reject
unsupported stats. Do not enable a new racewar bonus as part of this repair.

**Verify:** regular-only, maximum-only, mixed, reset, both sides, invalid side/stat,
capped/uncapped scaling, and the real caller when one is introduced.
[Setter](../../../src/combat/racewar_stat_mods.c#L62),
[application](../../../src/combat/racewar_stat_mods.c#L30),
[reset](../../../src/net/comm.c#L1182).

## F22 — Calming has a large one-point CHA cliff

**Status:** source verified; design decision. **Priority:** P3.
**Recommendation:** document first; smooth only through a balance decision.

CALMCHANCE divides CHA by 9 below 80, by 7 at 80..160, and by 4 above 160.
CHA **160 → 161** changes this term **22 → 40**. The 79/80 boundary also jumps.

**Gameplay:** one point across 160 can matter more than a large lower investment
for aggro avoidance. Callers still add their own gates/bonuses; 40 is not
universal 40% immunity.

**Fix:** retain/document if deliberate. If smooth progression is intended, use
a continuous piecewise formula anchored to approved values and review callers.
A surprising jump alone does not authorize removing the high-CHA reward.

**Verify:** 78/79/80/81, 159/160/161/162, aggression entry points, and stacking.
[Macro](../../../src/core/utils.h#L1428),
[caller](../../../src/cmd/interp.c#L3958).

## F23 — Low INT can make Awareness's computed duration zero

**Status:** helper reproduced; affect handling source verified. **Priority:** P3;
threshold/design question. **Recommendation:** clarify or floor the multiplier.

Duration is multiplied by integer `STAT_INDEX(INT)/9`. Below effective INT 51,
the index is below 9 and the result is zero. At level 56/skill 100, INT **50 → 51**
changes maximum duration **0 → 10 game ticks**. The command still adds the affect;
zero-duration normal affects wear off at a subsequent update, not necessarily
immediately.

**Gameplay:** low-INT/debuffed users can spend an action for only the remainder
of an update interval, then get a large increase at 51. Most normal undepleted
high-level builds exceed this boundary. Restricted low-INT races and other stat
reductions warrant checking, subject to class eligibility.

**Fix:** if a positive rolled duration is intended, floor the multiplier or
duration at one. Otherwise describe the deliberate low-INT penalty accurately.

**Verify:** INT 50/51, indices 8/9 and 17/18, levels/ratings, activation and
expiration timing. Integer plateaus are not gradual improvements.
[Duration](../../../src/classes/new_skills.c#L423),
[application](../../../src/classes/new_skills.c#L465),
[expiration](../../../src/magic/affects.c#L4172).

## F24 — Stat comments and descriptions disagree with active formulas

**Status:** source verified. **Priority:** P3. **Recommendation:** correct
descriptions before changing runtime behavior.

- Shatter/Shriek say POW 92..100 has no bonus, but index 16 minus 15 gives **+1**.
  NewSaves multiplies this by five threshold points, making resistance harder.
  Decide whether 15 or the comment is intended; preserve behavior and correct
  the comment by default. Shatter can damage gear on failure, so a formula change
  affects more than damage magnitude.
- Melee's critical comment says INT 100 gives 5% and 200 gives 25%; the macro
  gives **8% and 28%** before confirmation. Hypothetical 100% discussion also
  exceeds the ordinary INT ceiling's 90% initial threshold.
- Quick Thinking says failed saves reroll. NewSaves does reroll failure;
  StatSave instead gives INT/POW an initial 15% automatic pass and one ordinary
  roll, without rerolling other failed stat saves. Scope the description to
  those distinct benefits.
- Old DEX attack ladders, reduced-range STAT_INDEX, alternate psionic recovery,
  class-minimum-based PC rolling, and `wipe2011` notching are inactive in the
  standard checkout. Do not derive racial balance or guidance from them.

**Gameplay:** misleading numbers change investment/counterplay expectations.
Inactive code is not an extra live benefit or defect.

**Fix:** correct stale comments and scope the innate description accurately.
Treat any resulting formula adjustment as a separate balance decision.

**Verify:** active branches, effective ceilings, and exact random ranges;
change runtime odds only through a separate intended behavior change.
[Shatter](../../../src/magic/magic.c#L18359),
[Shriek](../../../src/cmd/actoff.c#L13856),
[critical macro](../../../src/core/utils.h#L1426),
[critical use](../../../src/combat/fight.c#L8036),
[Quick Thinking](../../../src/core/utility.c#L3224),
[StatSave](../../../src/core/utility.c#L3340),
[NewSaves](../../../src/net/sparser.c#L1307),
[inactive roller](../../../src/cmd/actwiz.c#L5620),
[conditional notching](../../../src/guild/guild.c#L215).

## F25 — High-CON boulder knockout can be applied without an expiry event

**Status:** duration boundary reproduced; application-to-scheduler failure chain
source verified. **Priority:** P1, conditional on encountering this procedure.
**Recommendation:** fix before other stat tuning.

The boulder special calls `KnockOut(victim, number(2,25-STAT_INDEX(CON)))`.
The random helper supports reversed endpoints; it does not clamp the upper
endpoint to two. At CON 197..208 the upper endpoint is zero. At **CON 209** it
becomes -1; CON 511 gives a range **-26..2**, with 26 negative outcomes out of 29.

`KnockOut` applies the knocked-out bit and an `AFFTYPE_SHORT` affect, passing
that duration through without validation. `affect_to_char` adds the affect
before scheduling its expiry. The scheduler rejects negative delays, and the
return is ignored here. Normal affect updates skip short affects because their
events are supposed to remove them.

**Gameplay:** raising CON can turn a brief knockout into one with **no scheduled
wake-up**. Knockout restricts commands and standing; normal ticking cannot
expire this failed short-affect instance. This is not a claim of permanent
save-file corruption or of an observed trapped player. Other removal/recovery
paths and a real encounter were not exercised. The boulder's target, hit, and
knockout gates must all pass; the negative-duration fraction is conditional on
those gates. Ordinary high-CON races can approach this range, so it is not only
a stat-511 concern.

**Fix:** bound the caller's upper duration with `max(2,25-index)` as the falling
injury path already does for its own duration formula. Also make short-affect
application handle a failed expiry schedule without leaving an incapacitating
affect behind. Preserve immediate-expiry semantics where zero is intentional;
do not remove the scheduler's valid rejection of negative delays.

**Verify:** CON around 184/185, 196/197, 208/209, and 511; force every duration
outcome; confirm a wake-up event and actual bit removal; inject scheduling
failure and confirm rollback/recovery. Include command/stand behavior and the
procedure's target-selection gates. The existing scheduler regression passed
its real negative-delay rejection and short-affect cases; this review did not
execute the complete boulder-to-player journey.
[Boulder duration](../../../src/specs/specs.mobile.c#L5688),
[random endpoints](../../../src/core/random.c#L91),
[KnockOut](../../../src/magic/affects.c#L3656),
[affect before schedule](../../../src/magic/affects.c#L2054),
[scheduler rejection](../../../src/world/new_events.c#L830),
[normal update skips short affects](../../../src/magic/affects.c#L4170),
[command restriction](../../../src/cmd/interp.c#L1985),
[bounded falling duration](../../../src/world/falling.c#L82),
[scheduler regression](../../../tests/async/test_nevent_scheduler_runtime.py#L723).

## F26 — Warhorse's second avoidance check reads the horse's AGI

**Status:** source verified; likely wrong-subject check. **Priority:** P2 if
the procedure is used. **Recommendation:** use the intended defender.

After a target saves against the warhorse's overbearing charge, the unmounted
follow-up branch decides whether to stop or drop through to a mule kick using
`rider || number(0,4) || StatSave(ch,APPLY_AGI,-2)`. Here `ch` is the horse,
although the messages credit the target's dodge. The first charge save and the
independent mule-kick case correctly check `vict`.

**Gameplay:** after the first successful dodge, higher horse AGI helps the target
avoid the follow-up, while the target's racial/MAX AGI no longer controls that
second check. A less agile horse can become more dangerous in this narrow path.
A rider or the 4-in-5 random stop already prevents follow-up; this is not every
warhorse attack, nor a claim that the initial target AGI save is ignored.

**Fix:** change that save to `StatSave(vict,APPLY_AGI,-2)` if it is another defender
dodge. If intended as horse recovery, use an explicitly described horse check
with the appropriate success direction rather than crediting a target dodge.

**Verify:** force the first save to pass, no rider, and the random gate to zero;
vary target and horse AGI independently, then cover rider/random-stop and the
ordinary mule-kick branch. Check procedure assignment before estimating usage.
[Charge and follow-up](../../../src/specs/specs.mobile.c#L8284),
[wrong subject](../../../src/specs/specs.mobile.c#L8348),
[ordinary mule kick](../../../src/specs/specs.mobile.c#L8379).

## Already fixed since the stats analysis

**Shield block's uninitialized/dead `percent` path is resolved here.** Commit
`04ed51869` removed the unused posture/Luck/Bless calculation and uninitialized
temporary, and made an improved counter count as a block even when both survive.
Current melee block uses the DEX/STR score contest without that retired Luck
term. Ranged arrow block still separately includes Luck.

**Gameplay:** do not file the old undefined-variable defect as open or count its
dead Luck term in racial comparisons. Adding a Luck/Bless melee bonus would be
a new behavior change. The current `test_medium_combat_effects.py` passed,
including shield-block and surviving-counter cases. The companion's old warning
is superseded by this recheck.
[Melee block](../../../src/combat/fight.c#L9570),
[arrow block](../../../src/combat/range.c#L538),
[regression](../../../tests/async/test_medium_combat_effects.py).

## Reviewed behavior that does not establish another bug

- **Opposite save signs are intentional API contracts.** Positive StatSave helps
  the defender; positive NewSaves hurts it. Ordinary POW_DIFF has the right sign
  for StatSave. Siren Song's CHA-minus-targetPOW has the right sign for NewSaves.
  Fix F10/F11's callers instead of reversing an API globally.
- **Racial scaling of base/fixed applies, MAX affecting current and cap, and
  POW×INT mana** are explicit balance rules. Unequal MAX-gear returns do not
  alone establish bugs.
- **Racial CON versus equal effective CON, original versus Planetbound Illithid
  HP, and Human +5** are explicit separate paths. Different results do not by
  themselves prove mistaken race mappings.
- **Buckets, caps, DEX/weight attack gates, STR spell bands, and WIS MR/parry
  plateaus** are not automatically defects when another point stops helping
  one consumer; other consumers can still improve.
- **Karma has no ordinary outcome consumer found in the companion census.**
  Orog's lower Karma and omission from Human/racewar bonuses do not demonstrate
  an ordinary combat penalty. Adding Karma mechanics is feature work.
- **Pet-duration expressions often read pet INT; NPC reactions read NPC stats.**
  These are not missing PC-owner racial bonuses merely because they read a
  different actor.
- **Temporary real-race persistence and size defects** remain in
  [race-size-issues.md](race-size-issues.md). Race changes can affect scaling,
  but those defects are not duplicated as new stat bugs. Corpseform is disabled.

## Verification, limits, and follow-up

Coverage includes the companion's ten review priorities and additional suspicious
boundaries: shops/Barter, factor/equipment scans, save APIs and stat-dependent
callers, HP/AC curves, Luck checks/caps, beast admission, regular/MAX apply units,
unarmed attacks, attributes, Awareness, warhorse/boulder procedures, and
dormant/configuration/comment paths.
This is a best-effort inventory from that analysis, not proof that the entire
codebase has no other bugs.

Verification performed:

- Compared the reused probe's effective-stat block, active STAT_INDEX, HP, mana,
  and normal AGI-defense function with current source before relying on them.
- Ran extracted-code C++ probes under ASan/UBSan for shop guards, weak override,
  HP curve/ignored-slot factor, Luck cap sequence, Feeblemind loss/rescaling,
  Awareness, StatSave comparison, psionic modifiers, Sanguinis POW, both Luck
  predicates, beast admission, boulder duration bounds, and configured final AC.
  Some cases execute a predicate/block with fixtures rather than the complete
  owning function.
- Enumerated Luck/save ranges for the fractions above. Swept 37 PC AGI factors
  and AGI 1..511 for the unscaled stat-only AC expression (18,907 cases); it is
  monotonic. Adding the actual negative-AC multiplier reproduced F08, so that
  narrower result is deliberately not a claim about final armor monotonicity.
- Passed `python3 tests/async/test_medium_combat_effects.py`, confirming its
  scoped combat cases and the already-landed shield-block repair.
- Passed `python3 tests/async/test_nevent_scheduler_runtime.py`, including actual
  negative-delay rejection and short-affect expiry/fallback cases under ASan/UBSan.
- Checked Markdown links, line-anchor bounds, issue coverage, whitespace, and
  the race folder index entry.

Probe source/output are local ignored artifacts in
`bin/tests/race-stats-issues-review/`. Durable counterexamples are above. HP
fixtures hold level, class, base/precalculated HP, gear, toughness, and other
bonuses fixed as stated; they are not predictions of a real player's total HP.

No full build, database test, live gameplay journey, deployed-setting check,
equipment-availability census, GitHub issue, or deployment was performed for
this review. Source-verified/design entries need their
proposed focused regressions when implemented. Check restricted builds and
special-procedure usage before estimating encounter frequency.
