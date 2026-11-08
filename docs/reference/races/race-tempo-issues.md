# Race tempo: potential bugs, gameplay impact, and recommended fixes

Reviewed 2026-11-08 against
`7546d23336e1f60b3b07771a1c39408272666cb5` and the current worktree.
Companion to [race-tempo.md](race-tempo.md), covering the timing systems used
by all 37 PC races. This report makes **no gameplay or configuration changes**.

There are **18 findings/review items** below. They are not 18 proven unintended
gameplay bugs: some are reproduced defects, some require a particular
configuration/build, and some need a timing-policy decision. Existing findings
from the other racial layers are collected in F18 without presenting them as
new discoveries. Reviewed timing behaviors that do not justify a fix are
recorded separately at the end.

## Evidence and recommended order

- **Reproduced:** extracted production functions/expressions or their relevant
  state transition ran locally. Dependencies such as the scheduler, world and
  equipment are fixtures; this does not establish a live incident.
- **Source verified:** the cited code contains the condition or inconsistency;
  the complete gameplay journey was not executed.
- **Conditional:** requires a specified configuration, skill total, gear total,
  resource state or class combination. Unverified content reachability is stated.
- **Design decision:** current behavior is established but historical intent is
  not. A numerical surprise alone does not authorize a rebalance.

**P1 conditional** identifies a server-crashing arithmetic path if an invalid
attack-share setting is accepted. **P2** means an active state, action or tuning
consistency problem. **P3** covers presentation, lower-impact timing policy and
narrow conditional cases. Priorities do not measure production frequency.

Recommended starting order:

1. Repair cast-event ownership and reduced-attack slot selection (F01–F02).
2. Reject unsafe attack-share values and count launched arrows correctly
   (F03–F04).
3. Make tuning/revert refresh the affected characters consistently (F06–F07),
   then address recovery floors and supported mastery interactions (F08/F10).
4. Correct misleading facts/displays and clamp the mastery outcome domain
   (F11–F12/F16–F17).
5. Decide the intended contracts for the nonlinear curve, ordinary durations,
   Druid/Blighter recovery and Haste/Slow before changing balance
   (F05/F09/F13–F14).

## F01 — A cancelled cast leaves a failure event that can cancel the next cast

**Status:** reproduced with production cancellation/callback functions and a
scheduler fixture. **Priority:** P2. **Recommendation:** fix.

`do_cast()`/`do_will()` can schedule `event_abort_spell` for a highest-circle
cast when the AGI-dependent concentration check fails. That event belongs to
the character and carries no cast identity. `show_abort_casting()` cancels
`event_spellcast`, but not `event_abort_spell`. Ordinary `StopCasting()` and
manual `do_abort()` therefore leave the old failure event behind. The old
callback unconditionally calls `StopCasting()` when it eventually fires.

**Gameplay:** with manual abort enabled, a player can abandon a sufficiently
long vulnerable cast, finish the four-second abort wait, begin another cast,
and lose that second cast to the first one's pending failure. For example,
an old failure due at pulse 30 can outlive an abort at pulse 1 and interrupt
a replacement admitted at pulse 18. This requires the original concentration
failure to have been scheduled; at AGI 100 or above its ordinary threshold
cannot fail. Slower races/casts create a larger window for the stale event.
Even with no replacement cast, the event can print a misleading concentration
failure. `StopCasting()` also reaches active item cancellation if such a route
is enabled.

**Fix:** cancel the cast's failure event on every terminal path, including
manual abort and broken target links, and ensure a failure callback cannot
terminate a different activation. Use the existing event cancellation/ownership
machinery. Scheduler-rejection cleanup already cancels this event, but normal
cancellation does not.

**Verify:** scheduled failure → early abort → replacement cast; broken target
link; completion/cancellation without a replacement; same-tick completion;
and a subsequently started active item action. Preserve the intended manual
abort wait and the new cast's own failure event.
[Failure scheduling](../../../src/net/sparser.c#L2410),
[cast scheduling](../../../src/net/sparser.c#L2910),
[normal cleanup](../../../src/net/sparser.c#L1329),
[manual abort](../../../src/net/sparser.c#L1407),
[unscoped callback](../../../src/net/sparser.c#L2977).

## F02 — Halving attacks duplicates early weapon slots instead of selecting a subset

**Status:** reproduced production selection expressions; active with committed
0.5 settings. **Priority:** P2. **Recommendation:** fix.

After building the ordered attack list, `perform_violence()` computes
`real_attacks=ceil(count*share)` and `div_attacks=int(1/share)`, then executes
`attacks[i/div_attacks]`. At share .5, eight attacks become four executions of
indices **0,0,1,1**. These are repeated early entries, not four different
entries from the eight-attack list.

**Gameplay:** inertial barrier, armlock and intercept change weapon composition
as well as attack count. A four-hand list such as primary/third/secondary/fourth
can repeat primary/third while losing the later weapon opportunities. A Monk
pressure-point entry in an early slot can also be repeated. Which side benefits
depends on weapon damage, effects and list order; this is not uniformly a nerf.
Combat Mind's committed .75 floor changes the integer divisor to 1, so it can
alter composition abruptly as well as restoring some attacks.

**Fix:** execute an explicitly chosen subset of the original attack list, without
unintentionally duplicating entries. Decide whether that means evenly spaced,
ordered-prefix or another documented selection; preserve intended weapon/Monk
semantics. Simply replacing division by multiplication only handles some shares
and should not be used without checking arbitrary supported fractions.

**Verify:** distinct labeled slots at counts 1–12 and shares .5/.75/1, odd-count
rounding, four hands, dual wield, Monk special entries, Combat Mind and target
death mid-round.
[Share calculation](../../../src/combat/fight.c#L11135),
[slot selection](../../../src/combat/fight.c#L11235),
[committed shares](../../../lib/duris.properties#L163).

## F03 — Accepted attack-share configuration can cause division by zero

**Status:** conditional undefined behavior reproduced under UBSan.
**Priority:** P1 conditional. **Recommendation:** reject invalid settings and
make the execution path safe.

The same calculation assumes a share in a suitable positive range but does
not enforce it. A value **1.2** produces `div_attacks=int(1/1.2)=0`; the first
`i/div_attacks` then divides by zero. Zero/nonfinite values also make the
reciprocal/conversion unsafe. The general `properties set` path accepts parsed
floats for these keys without a corresponding range check.

**Gameplay:** an operator trying a 20% attack increase through
`attacks.default.multiplier=1.2`, or an invalid override of another share, can
turn the next applicable combat round into a server failure. **Committed
values 1.0/.5/.75 do not trigger this division-by-zero case.** No production
setting was inspected or changed.

**Fix:** establish the supported domain and reject invalid values before
publishing them. If these are reduction shares, require finite `0 < share <= 1`.
If zero means complete suppression, handle it explicitly without a reciprocal.
If increases are intended, define attack expansion separately from the current
subset arithmetic. Keep a safe runtime fallback for invalid loaded state.

**Verify:** negative, zero, tiny positive, .5, .75, 1, 1.2, NaN/infinity through
configuration admission and the consumer; no undefined conversion, division or
out-of-bounds attack selection.
[Consumer](../../../src/combat/fight.c#L11151),
[property admission](../../../src/world/properties.c#L561).

## F04 — A lethal arrow is omitted from the volley recovery calculation

**Status:** source verified loop path; counter/lag arithmetic reproduced.
**Priority:** P2. **Recommendation:** fix the count.

The firing loop breaks on a non-`DAM_NONEDEAD` result before incrementing `i`.
After the loop, recovery uses `delay=i/3.0`. On that path, `i` is the zero-based
index of the final launched arrow, rather than the number launched. Running out
of ammunition before a launch is a different path and must not be charged for
an arrow that did not fire.

**Gameplay:** with integer melee value 17, no hidden/combat multiplier and the
committed divisor, a first-arrow kill requests **4 pulses** of lag rather than
the **9** produced by counting its one launched arrow. A third-arrow kill gives
15 rather than 21 pulses. This discounts finishing volleys, changes repeat
tempo across targets, and reduces the racial recovery difference on the
first-arrow case. The explicit intent to charge only fired arrows does not
explain treating a fired lethal arrow as zero.

**Fix:** track completed launches explicitly, including misses and a lethal
last shot. Do not use hit count, because misses also consume a launch. Apply
that count to surviving-actor recovery while retaining existing death exits.

**Verify:** death on the first/middle/final arrow, misses, ammo exhaustion before
a shot, returning arrows, hidden/fighting multipliers, and actor death.
[Break before increment](../../../src/combat/range.c#L1176),
[lag calculation](../../../src/combat/range.c#L1300).

## F05 — Enough pulse gear can make a slower racial/class base faster

**Status:** reproduced arithmetic; obtainable equipment totals not established.
**Priority:** P2 design review. **Recommendation:** decide whether ordering must
be monotone before tuning raw racial values.

The transform is `F=B+P*A(B)`, where
`A(B)=(.04/3)B²-(1.10/3)B+2.73`. Its response to B is
`1+P*((.08/3)B-1.10/3)`. With sufficiently negative P this can become negative:
improving the base interval can make the final interval worse.

**Gameplay:** in C=0 fixtures, Human/Ogre recurring intervals are 18/22 pulses
at P=0, but **15/14 at P=-8**, and **14/12 at P=-10**. At P=-20, Ogre reaches
the four-pulse minimum while Human remains at 11. For an Ogre P=-10 fixture,
Warrior's offset 0 gives interval 12 while Shaman's nominally slower +1 gives
11. Multiclass selection chooses the smallest *base* class offset, which need
not be the fastest transformed result in this region.

This is more than ordinary integer rounding, but it may reflect deliberate
compensation for slow bases. The source review did not prove a legal equipped
P=-8/-10 set for each race, so these are conditional balance outcomes rather
than measured live advantages.

**Fix:** if “lower base is faster” is the intended invariant across supported
builds, choose a monotone transform or bound the supported apply domain and
retune deliberately. Preserve desired low-gear differences and inspect the
floor. Do not replace the formula casually: it changes every pulse-bearing
build, including Hatred, class overlap and ranged recovery.

**Verify:** all 37 races × legal class offsets × attainable P totals, neighboring
base values, integer boundaries and minimum-floor saturation. Report both
actual gear reachability and pure formula behavior.
[Formula](../../../src/core/utils.h#L1410),
[selection and ordering](../../../src/magic/affects.c#L1887),
[worked tempo comparisons](race-tempo.md#b-one-more-pulse-apply-can-do-nothingor-save-a-quarter-second).

## F06 — Property set/revert changes the tables without refreshing cached rounds

**Status:** source verified; loader/cache divergence reproduced in a fixture.
**Priority:** P2. **Recommendation:** fix propagation for cached consumers.

`properties set` and `properties revert` call `apply_properties()`, which
rebuilds racial/class timing tables but does not recalculate every character's
`base_combat_round`. `properties reload` explicitly queues character
recalculation, and `pulse adjust melee` has its own narrower loop. The command
routes therefore do not have equivalent effective results.

**Gameplay:** two otherwise matching characters can use different melee timing
until an unrelated affect/equipment change recalculates one. A tuning experiment
can appear ineffective or gradual for accidental reasons. Reverting a table
does not necessarily restore the already-cached character value either.
In the fixture, Human's cached F remains 17 after its loaded R changes 15→10;
after recalculation F=12, reverting R to 15 leaves F=12 until another recalc.

**Fix:** queue recalculation for the characters affected by these cached timing
changes and by their rollback. Reuse the existing recalculation path. This is
distinct from rescaling an already-running `combat_tics`, which can reasonably
retain its current-cycle deadline.

**Verify:** set, reload and revert for racial/class/global melee keys; multiple
existing characters; unchanged characters; subsequent round resets; save/reload
and rollback. Do not rely on equipping an item to make a tuning command apply.
[Set/revert](../../../src/world/properties.c#L608),
[reload contrast](../../../src/world/properties.c#L623),
[cached tables](../../../src/world/properties.c#L147),
[cached round](../../../src/magic/affects.c#L1890).

## F07 — Pulse adjustment misses shared-key and mechanics-race consumers

**Status:** source verified; shared-key resolution reproduced.
**Priority:** P2. **Recommendation:** refresh by effective dependency.

`pulse adjust melee` refreshes only characters whose `GET_RACE` equals the
selected race ID. PC Vampire and NPC Vampire share the property key
`damage.pulse.racial.Vampire`; the loader updates both entries, but name
resolution selects the earlier PC ID and the refresh loop skips the other ID.
The tutorial-mobile mechanics-race override is another case where the table
consumer can differ from the stored race checked by this loop.

**Gameplay:** the command can advertise one shared value while existing NPCs
or copied race profiles retain a different cached round. That distorts PC/NPC
and training-profile comparisons. Casting reads its table on new casts, so the
same cache issue does not apply identically to `pulse adjust cast`.

**Fix:** identify all consumers of the changed property/mechanics race, or use
the existing all-character recalculation approach for this infrequent staff
operation. Do not silently split the Vampire property into new keys unless
separate tuning is an explicit design choice.

**Verify:** PC/NPC Vampire aliases, the copied tutorial profile, an ordinary
native race, old/new character instances and both adjustment types.
[Shared names](../../../src/core/common.c#L79),
[name resolution](../../../src/world/racial_pulse.c#L50),
[refresh filter](../../../src/world/racial_pulse.c#L194),
[mechanics-race selection](../../../src/specs/specs.ailvio.c#L32).

## F08 — Spell recovery can calculate and schedule zero-pulse intervals

**Status:** reproduced production Tupor calculation; content-dependent stat
reachability. **Priority:** P2/P3. **Recommendation:** define and enforce the
minimum at the scheduling boundary.

Recovery formulas truncate to integers without the casting function's final
one-pulse floor. Explicit assimilation/Tupor then halves the first interval.
With Harpy's committed INT baseline 120, level 56 and a non-semi-caster INT
recovery fixture, circle 1 gives interval **5 at INT120**, **1 at INT150**, and
**0 at INT190**. The first recovery at INT150 schedules `1/2=0`; sleeping prone
also makes that computed one-pulse interval become zero. These figures do not
establish an actual equipped build or availability of every fixture class.

**Gameplay:** a replenishment can happen in the current event pass if requested
before it, whereas a subsequent zero-delay rearm waits until the next tick.
Recovery speed becomes sensitive to entry phase and can converge on one slot
per loop. The scheduler prevents infinite same-pass recursion; this is not a
claim of unlimited instantaneous refill. Display estimates that clamp steps
to at least one pulse can differ from the initial zero-delay execution.

**Fix:** decide the minimum recovery interval and apply it after all relevant
halving/multiplication, where events are scheduled. A modest one-pulse minimum
would eliminate the zero-delay boundary without pretending that faster casting
also speeds regeneration. Preserve the intentional first-slot policy otherwise.

**Verify:** duration 0/1/2, high-stat and sleeping/meditating cases, first versus
subsequent slots, highest-circle-first order, and displayed remaining time.
[Tupor formula](../../../src/classes/memorize.c#L682),
[first-slot scheduling](../../../src/classes/memorize.c#L1590),
[rearm](../../../src/classes/memorize.c#L1149),
[estimates](../../../src/classes/memorize.c#L1384).

## F09 — Ordinary affect durations include a separate zero-duration interval

**Status:** source verified; duration-contract decision. **Priority:** P2/P3.
**Recommendation:** settle semantics before changing the update loop.

The ordinary update decrements duration N through zero, then waits until a
later eligible pass to remove it. For PCs those passes are 75 seconds apart.
An ordinary duration 1 therefore lasts approximately **75–150 seconds**;
duration 5 lasts **375–450 seconds**. A short affect with 300 pulses instead
has a nominal 75-second deadline.

**Gameplay:** both buffs and debuffs can last up to another full update interval
beyond the simple duration×75 interpretation. Short durations get the largest
proportional difference. Uptime/cooldown comparisons and player descriptions
can be wrong if they assume removal on the decrement to zero. Many existing
values may have been tuned around the current behavior.

**Fix:** either explicitly define the legacy zero-duration interval and display
honest bounds, or migrate to removal when a positive duration becomes zero with
an audit of existing durations and persistence. I recommend documentation and
contract tests first; a global decrement-order change is a broad rebalance.

**Verify:** N=0/1/5, application just before/after the PC update phase, short
versus ordinary flags, refresh, offline rules and restoration.
[Update](../../../src/magic/affects.c#L4123),
[zero-removal branch](../../../src/magic/affects.c#L4172),
[tempo interpretation](race-tempo.md#event-timing-and-ordinary-affect-expiry).

## F10 — Owning Chant Mastery can suppress another acceleration even when it fails

**Status:** source verified; relevant to supported overlapping skill ownership.
**Priority:** P2 conditional. **Recommendation:** make failure fallback explicit.

`do_cast()` selects the Chant Mastery branch whenever its effective rating is
nonzero. A failed mastery proc returns the original duration and installs its
wait, but does not fall through to Totemic Mastery, Nature's Sanctity or Nature's
Ruin. Their single-class grant lists differ; however, epic reward eligibility
accepts the primary **or secondary** class, so overlapping ownership is a real
supported class-system possibility, not just a comparison of unrelated classes.

**Gameplay:** a multiclass character can lose an otherwise successful terrain/
totem acceleration by learning another supposedly helpful skill. In a fixed
20-pulse fixture, a successful .75 branch would give 15 pulses; a failed
Chant Mastery roll instead leaves 20 and prevents that later check. Actual
benefit across all rolls depends on mastery rating and the other skill.

**Fix:** decide whether mastery should have exclusive priority on ownership or
only on a successful proc. I recommend allowing later applicable acceleration
after failure, while preserving the chosen nonstacking rules on success.
Avoid granting every bonus simultaneously as an incidental repair.

**Verify:** each supported overlapping class/skill combination, forced mastery
success/failure, terrain/totem states, Quick Chant afterward and both landing
and command-recovery times.
[Branch ordering](../../../src/net/sparser.c#L2828),
[failed mastery](../../../src/classes/epic_skills.c#L1314),
[class grants](../../../src/classes/epic_skills.c#L86),
[secondary-class eligibility](../../../src/classes/epic_skills.c#L244).

## F11 — Boosted mastery ratings can produce an unhandled outcome above the best tier

**Status:** reproduced helper/handler behavior; ordinary learned ceilings and
content availability limit exposure. **Priority:** P3 conditional.
**Recommendation:** bound the outcome to its supported domain.

Chant Mastery and Spatial Focus calculate
`max(0, effectiveSkill/40 + roll(-1,1))`. Their consumers distinguish exactly
3/2/1 and use the low-result branch for everything else. At effective skill
120, result 4 is possible and falls into that low branch. The effective-skill
lookup permits additive/granted bonuses above learned rating; no specific
currently obtainable +20 mastery item was established by this review.

**Gameplay:** on a forced successful proc and +1 result roll, Chant Mastery
rating 119 gives **cast 1 / wait 1**, while rating 120 gives **cast 16 / wait 20**
for a 20-pulse input. More skill can produce a worse result. Spatial Focus
has the same out-of-range result and tier-dispatch shape. Normal learned
rating 100 alone does not reach result 4.

**Fix:** saturate the result at 3, matching the documented 0–3 domain, or
explicitly handle higher tiers as at least as good as the best. Keep the
normal probability/threshold behavior unchanged.

**Verify:** effective ratings around 39/40, 79/80, 119/120 and above, all three
result rolls, forced success/failure and removal of the boosting affect.
[Chant outcome/dispatch](../../../src/classes/epic_skills.c#L1228),
[Spatial Focus](../../../src/net/sparser.c#L2232),
[effective skill bonuses](../../../src/core/utility.c#L5219).

## F12 — Mastery and Spellweave facts misstate effect time or final recovery

**Status:** source verified presentation contradictions. **Priority:** P3.
**Recommendation:** fix facts; do not remove recovery to match them.

- Spatial Focus says lower-rating results only change the message, but results
  0/1/2 also change effect timing and/or the initial wait.
- Its best-result description, and Chant Mastery's one-pulse lag description,
  omit the normal successful spell-completion wait of four pulses. One-pulse
  mastery landing does not mean the actor is free one pulse after starting.
- Spellweave says releasing the stored spell has “no lag.” The immediate branch
  still calls `event_spellcast()`, whose normal completion tail requests that
  four-pulse recovery.

**Gameplay:** players can overvalue repeated casting speed, undervalue lower
mastery tiers, or expect to perform a follow-up action before the command gate
actually clears. These inaccuracies are especially material near fast racial
casting floors.

**Fix:** report effect delay, initial wait and ordinary completion recovery
separately. Label branch-specific values rather than presenting them as the
whole action cycle. Preserve any spell-specific extra waits and early returns.

**Verify:** low and high skill facts against traced outputs; woven release;
ordinary cast/will; queued next action. The tempo layer's wait fixtures confirm
the ordinary `max(W, landing+4)+1` next-input calculation under stated conditions.
[Spatial facts](../../../src/net/sparser.c#L2244),
[Spatial effects](../../../src/net/sparser.c#L2299),
[Chant facts](../../../src/classes/epic_skills.c#L1271),
[Spellweave facts](../../../src/net/sparser.c#L2555),
[completion wait](../../../src/net/sparser.c#L3449).

## F13 — Druid and Blighter automatic quick-casting use different wait formulas

**Status:** source verified; intended class asymmetry uncertain.
**Priority:** P2/P3 design decision. **Recommendation:** specify the contract.

On their ordinary branches, both single-class Druid and Blighter receive the
later automatic halving of effect time. Druid's initial wait is `floor(D/2)+6`;
Blighter normally retains D. Earlier mastery/nature branches can supersede
these cases. Both still face ordinary completion recovery.

**Gameplay:** with D=18, both land at pulse 9, but the ideal next queued starts
are **16 for Druid versus 19 for Blighter**. At D=6, the direction reverses:
both land at 3, but next starts are **10 versus 8**. Racial factors and gear
can therefore move a build across a reversal in this class comparison, even
though both are described as automatically quick-casting.

**Fix:** if the two paths are meant to share a timing policy, align both effect
and recovery calculations. If the asymmetry is intentional, document its fixed
six-pulse component and crossover. Do not assume every class must have equal
recovery merely because it shares Quick Chant behavior.

**Verify:** small/large D, odd durations, racial factors, Haste, both classes,
single versus multiclass and earlier mastery/nature branches.
[Wait branches](../../../src/net/sparser.c#L2828),
[shared halving](../../../src/net/sparser.c#L2898),
[worked cast model](race-tempo.md#c-a-spell-lands-earlier-than-the-character-becomes-ready-again).

## F14 — Simultaneous Haste and Slow have inconsistent timing consequences

**Status:** source verified interaction; design decision. **Priority:** P3.
**Recommendation:** define precedence across consumers and delivery paths.

Slow can be added while Haste is present; the ordinary Slow spell does not
cancel Haste, and the Thri-Kreen cold-vulnerability path adds its own Slow
affect directly. The consumers then differ: non-Monk base-attack admission
accepts Haste despite Slow, the separate Haste extra attack requires no Slow,
casting still receives the .8 Haste multiplier, bard beats still use the faster
period, and non-Monk input polling is still slowed. Monk base attacks have
another Slow branch, while the ordinary Slow spell refuses Monks.

**Gameplay:** “Haste cancels Slow” is not a universal rule. A hasted Thri-Kreen
hit with the cold penalty can retain fast cast/song timing but lose command
opportunities and attack payload. Different Slow delivery paths can encounter
different immunity checks. This is not proof that all such differences are
unintended, nor that every class/race combination is normally available.

**Fix:** decide whether the bits cancel, coexist with explicit separate effects,
or have source-specific priority. Apply that decision consistently at the
owning boundaries and update facts. Do not replace every consumer with one
generic speed multiplier.

**Verify:** Haste only, Slow only, both in each application order, cold versus
ordinary spell delivery, Monk/non-Monk, casting, songs, archery, attack counts
and command input.
[Slow spell](../../../src/magic/magic.c#L10840),
[cold application](../../../src/combat/dam_mods.c#L727),
[attack consumers](../../../src/combat/fight.c#L10445),
[casting](../../../src/net/sparser.c#L995),
[song timing](../../../src/classes/bard.c#L60),
[input gate](../../../src/net/comm.c#L2189).

## F15 — The fixed melee-XP cadence has a shorter interval at pulse wrap

**Status:** source verified; cadence reproduced arithmetically. **Priority:** P3.
**Recommendation:** use the monotonic clock if exactly 16-pulse spacing is intended.

The periodic XP gate uses `pulse % PULSE_VIOLENCE == 0`, but `pulse` wraps at
`PULSES_IN_TICK=300`, which is not divisible by 16. The sequence includes
**272,288,300,316**, so the wrap interval is 12 pulses rather than 16.

**Gameplay:** the eligible melee-XP branch can run after three seconds at that
seam instead of four. There are 19 eligible phase positions per 75-second
revolution, versus 18.75 for an exact four-second cadence. This affects the
XP opportunity, **not the independently maintained racial attack countdown**;
the level, opponent and action-state eligibility checks still apply.

**Fix:** base a strictly periodic check on `ne_event_tick` or an equivalent
absolute deadline. Leave ordinary affect updates that deliberately use the
75-second phase alone. Decide whether preserving the existing average XP rate
requires retuning before changing the cadence.

**Verify:** several 300-pulse seams, exact event counts, blocked attackers and
unchanged automatic-attack timing across the seam.
[XP gate](../../../src/combat/fight.c#L11003),
[eligibility](../../../src/combat/fight.c#L11043),
[wrapping pulse assignment](../../../src/world/new_events.c#L1817).

## F16 — Pulse displays expose partial values that are easy to read as actual speed

**Status:** presentation/measurement gap. **Priority:** P3.
**Recommendation:** clarify units and add derived timing where useful.

`score` prints truncated `base_combat_round`, although steady recurring melee
uses that integer **plus one** scheduler pulse. Its Spell Pulse value is the
racial factor times the stored spell apply, without a chosen spell's truncation,
global factor, Haste/Flurry, mastery, completion wait or input phase. The staff
`pulse` table's “Round” adds the global offset but explicitly precedes class
adjustments; it is also not the complete runtime interval.

**Gameplay:** players/operators can infer the wrong actions per second or think
a pulse item is broken when it does not cross an integer boundary. Conversely,
an apparently small change can yield a discrete extra action. Raw values remain
useful for diagnostics, but comparing them as final DPS or repeat-cast speed
misleads race balancing.

**Fix:** label raw bases/factors clearly, expose the actual recurring melee
interval, and show spell-specific effect/recovery estimates only with their
conditions. Do not invent one universal casting-time number.

**Verify:** fractional F, floor saturation, +/− pulse applies, Haste/Flurry,
global override and several short/long spells; compare display to execution.
[Score](../../../src/cmd/actinf.c#L6745),
[staff table](../../../src/world/racial_pulse.c#L64),
[countdown](../../../src/combat/fight.c#L11056),
[casting function](../../../src/net/sparser.c#L995).

## F17 — Inactive settings and outdated timing labels can drive incorrect tuning

**Status:** maintenance/presentation. **Priority:** P3.
**Recommendation:** label or retire misleading inputs; preserve current mechanics.

The property file retains non-neutral `damage.totalOutput.racial.*` values,
but the loader explicitly sets the corresponding field to 1. Old direct-AGI
speed and pulse-compression switches are commented out. Timing constants also
retain incompatible prose: the 35-pulse bard constant says 15 seconds, while
4 pulses/s makes it 8.75 seconds; `WAIT_ROUND=12` differs from the 16-pulse
`PULSE_VIOLENCE`. Several code fallbacks differ from committed settings, such
as the global melee offset +1 versus +2 and Two Daggers -3 versus -1.

**Gameplay:** an operator can tune an inactive damage setting, infer nonexistent
compensation for a slow race, or compare durations using the wrong “round.”
An absent property can silently select a different balance from the checked-in
configuration. Different fallback values are not inherently wrong, but need
to be explicit in reproducible comparisons.

**Fix:** mark unused settings as inactive or remove them after checking remaining
references; correct units/comments and document important fallback behavior.
Do not reactivate retired racial multipliers or replace every round constant
as a documentation cleanup.

**Verify:** active-consumer search, missing-key fixtures, actual property snapshots
and unchanged output when removing an unused value.
[Disabled multiplier](../../../src/magic/affects.c#L3477),
[current pulse application](../../../src/magic/affects.c#L1965),
[clock constants](../../../src/core/config.h#L75),
[fallback loading](../../../src/magic/affects.c#L3510).

## F18 — Previously documented innate timing defects still affect these comparisons

**Status:** current source rechecked; overlaps the innate issue companion.
**Priority:** P2 for state defects, P3 for explicit policy questions.
**Recommendation:** fix in their owning paths, without counting them twice.

- **Troll-burn refresh:** writing the duration field does not move the short
  expiry event. Recent fire can fail to extend regeneration suppression.
  Refresh/replace the owning event. See [innate F03](race-innates-issues.md#f03--repeated-fire-does-not-actually-extend-troll-burn-expiry).
- **Shade Movement lifetime:** break paths clear cached flags without removing
  the ordinary affect; its state can return on recalculation. Remove the owning
  effect and reconcile direct stealth flags. See [innate F06](race-innates-issues.md#f06--shade-movement-loses-flags-without-losing-its-owning-affect).
- **Rejected-use costs:** some deterministic invalid/redundant attempts still
  consume long rests. Preflight known refusals while retaining costs for valid
  resisted/evaded attempts and changed delayed destinations. See
  [innate F10](race-innates-issues.md#f10--some-deterministic-refusals-still-spend-long-cooldowns).
- **Charge/Grave readiness:** the generic display ignores their skill-tag rests
  and can say ready while the command refuses. Read the actual timer source.
  See [innate F11](race-innates-issues.md#f11--generic-innate-status-misses-charge-and-call-of-the-grave-rests).
- **Sunlight and regeneration representations:** HP/mana/burn exemptions differ,
  and a real Regeneration affect changes combat recovery differently from the
  passive bit. These alter usable uptime but require a policy decision before
  making every source equivalent. See [innate F21](race-innates-issues.md#f21--sun-burn-hp-recovery-and-mana-recovery-have-different-exemptions)
  and [F26](race-innates-issues.md#f26--regenerations-combat-benefit-depends-on-affect-representation).

The already-fixed Bite key, Leap unlock and five rejected-use cases remain
resolved in this checkout. The newer tempo review does not reopen them merely
because the older mechanics document retains its original snapshot.

## Reviewed behaviors that are not established bugs

- **Melee's extra countdown step and integer plateaus:** current behavior is
  `trunc(F)+1`, including the one-second minimum at F=3. This is established
  engine behavior, not sufficient evidence to change it to `trunc(F)`.
  Changing it would accelerate every race and requires recalibration.
- **Quick Chant retaining initial lag and the post-cast floor:** these are
  explicit action-cost rules. Earlier landing can improve interruption safety
  or preserve a melee opportunity without halving sustained cast cycles.
  Correct misleading descriptions (F12), rather than assuming all recovery
  should be removed. Original Illithid's .025 factor is a configured outlier,
  not a demonstrated typo.
- **Commands and automatic attacks using different gates:** ordinary command
  lag does not universally stop PC melee. Casting/item activity and control
  have additional checks. Do not globally freeze attacks during every wait.
- **A suppressed melee opportunity is consumed:** the counter resets before
  several action gates. Casting can miss a round and wait for the next one.
  Preserving/banking every suppressed attack would introduce a new burst
  mechanic; current code alone does not justify that change.
- **Changing speed does not rescale every in-flight timer:** the next melee
  reset can use the new value while the current countdown keeps its old
  remainder. Existing casts/song beats similarly own scheduled work. That
  bounded transition is different from the indefinite stale cache in F06/F07.
- **Circle/Flank duration shrinks with faster melee:** these explicitly use
  one or three personal round intervals. They can have shorter real-time
  uptime against fixed command/reuse costs. Record that tradeoff; change to
  fixed seconds only if that is the chosen positional-buff design.
- **Fixed innate rests, first-use-window recharge and offline pause:** these
  are implemented cooldown policies. No logout-reset exploit or requirement
  to scale them with spell gear was established here.
- **Haste accelerating songs while consuming verses sooner:** a fixed verse
  count is not a fixed elapsed lifetime. This is a coherent tradeoff, distinct
  from obsolete clock comments and mixed Haste/Slow rules.
- **Whirlwind spending vitality on its round clock:** more frequent cycles can
  exhaust its reserve sooner. Its drain precedes some later attack-suppression
  checks, so maintaining the state can cost vitality without a delivered attack.
  Whether maintenance should be free on those blocked opportunities needs an
  explicit rule; this review does not infer that every failed opportunity must
  refund its resource cost.
- **Different casting and replenishment formulas:** faster spending can empty
  reserves sooner. There is no requirement for racial casting speed to multiply
  PSP/HP recovery or memorization speed. Double-counting those as speed benefits
  would distort balance.
- **Opt-in item-action timing:** committed master/device switches are off.
  Their fixed windup and real-time reaction floor are not a hidden active
  racial casting penalty. No new item-action timing defect was established.

## Coverage and verification

The review re-read all sections of the tempo layer and followed the suspicious
conditions into current consumers. Scope reconciliation:

| Tempo topic | Disposition |
|---|---|
| Clock units, update phases and expiry | F09/F15/F17; countdown/event distinctions retained |
| All 37 race settings, class offsets, applies and reload | F05–F07/F16–F17; no missing PC row found |
| Cast/will, mastery, failure, input and recovery waits | F01/F10–F14/F16; ordinary recovery policies retained |
| Attack payload and reduction | F02–F03; existing stat/body issues remain in their companions |
| Archery | F04; separate volley/pulse scaling retained |
| Songs, movement, pets and item actions | Clock/overlap findings above; no independent new defect established |
| Innate cooldowns and time-dependent racial benefits | F18 and existing resolved distinctions |
| Spell/resource recovery and between-fight tempo | F08/F18; separate resource models retained |
| Worked comparisons and every-race implications | Reconciled with the conditions and limits of the findings |

Local isolated probes under `bin/tests/race-tempo-issues-review/` exercised:

- Extracted production `show_abort_casting`, `StopCasting`, `do_abort` and
  `event_abort_spell`, demonstrating cancellation of a replacement cast.
- Production attack-share/slot expressions, including an intentionally invalid
  1.2 setting that UBSan diagnosed as integer division by zero. This was an
  isolated expected-failure probe, never a server configuration change.
- The production melee recalculation excerpt at negative applies, table reload
  versus cached values, and Vampire name/key resolution.
- Production Chant Mastery helpers/handler and Spatial Focus outcome helper
  at 100/119/120 effective rating.
- Production Tupor calculation with its real level table and active stat-index
  function, plus source-verified first-slot halving.
- Source-verified arrow-loop and wrapping-XP arithmetic fixtures. These prove
  the count/cadence calculations, not a full bow combat or XP journey.

`test_spell_schedule_failure_runtime.py`, `test_racial_pulse.py`, and
`test_tupor_display_runtime.py` passed in this review. Those checks cover their
existing contracts; notably, scheduler-rejection cleanup passing does not prove
normal cast cancellation removes a stale abort event. The broader timing and
scheduler checks recorded in the tempo reference are not reclassified as
reproductions of these newly identified defects.

Final verification passed for the finding sequence, local links/anchors,
whitespace, evidence outputs and source freshness. No live server, production properties,
SQL prototypes, player records or obtainable endgame equipment sets were
inspected. No runtime code was changed, no full server build was needed, and
no commit, push or issue filing is part of this report. “All potential bugs”
here means the candidate findings from this tempo-layer review, with explicit
dispositions; it does not assert that the entire MUD has no other timing bugs.
