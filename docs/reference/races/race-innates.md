# PC racial innates: mechanics and gameplay differences

Source review: 2026-11-08, checkout `b96dcdebbc9eb85a876c6bc64918b7a678d483d9`.
This reference follows all **37 PC race IDs, 188 racial grants, and 78 distinct
innates** from assignment through their active handlers, passive checks, applied
flags, downstream consumers, and expiry. It includes restricted/legacy PC races;
being in an old source block headed “NPC Races” does not make a PC ID an NPC.

Numbers below use checked-in properties and ordinary mortal behavior. They are
source-derived mechanics, not measured race win rates or a claim about deployed
property overrides. Gameplay and configuration are unchanged by this document.
[PC boundary](../../../src/core/defines.h),
[assignments and names](../../../src/classes/innates.c#L147),
[creation policy](../../../lib/creation_availability.cfg#L46).

Companions: [racial stats](race-stats.md), [racial size](race-size.md),
[stat issues](race-stats-issues.md), and [size issues](race-size-issues.md).
Stats, native size, class eligibility, racial damage/speed/XP factors, racewar
membership, undead identity, extra arms and native equipment exclusions are
separate rules. This document includes those where an innate invokes or changes
them; it does not count every non-innate racial advantage as another innate.

Navigation: [unlock roster](#2-complete-race-by-race-unlock-roster),
[senses and concealment](#3-senses-information-and-concealment),
[travel and bodies](#4-flight-breathing-bodies-and-physical-access),
[defenses and recovery](#5-defense-saves-recovery-and-vulnerabilities),
[offensive passives](#6-offensive-passives-weapon-choices-and-group-scaling),
[physical actions](#7-physical-attacks-control-and-doors),
[spell-like powers](#8-spell-like-powers-forms-and-travel),
[summons and economy](#9-summons-images-equipment-and-economy),
[race comparisons](#10-what-the-differences-mean-for-each-race),
[reuse index](#11-active-innate-cost-and-reuse-index),
[lifecycle](#12-lifecycle-boundaries-and-interpretation),
[verification](#13-evidence-verification-and-limits).

## 1. Reading the mechanics

### Ownership, unlocks and commands

`assign_innates()` clears and fills the racial and class tables. `has_innate()`
compares current level with the **earliest** eligible racial, base-class or
specialization grant. A base-class grant remains available after specialization;
a duplicate racial/class grant does not produce two copies, two proc rolls, or
separate cooldowns. Multiclass ownership checks all owned classes. A table entry
is an unlock requirement, not a trained percentage or automatic success chance.
[Lookup](../../../src/classes/innates.c#L381),
[specialization regression](../../../tests/async/test_innate_specialization.py).

The innate race normally follows the mechanics race, with a shape disguise using
`disguise.race`. Corpseform's regular-innates mode instead reads the saved race in
`TAG_RACE_CHANGE`; corpseform itself is disabled at its current entry point.
Handlers that explicitly inspect `GET_RACE` or `GET_RACE2` can then select a
variant or reject use. Ownership through a shape therefore does not guarantee
all native-race implementation branches agree.
[Race selection](../../../src/classes/innates.c#L381),
[corpseform entry](../../../src/classes/necromancy.c).

Use `race innates <race>`, `innate`, and `innate info <name>` to inspect grants,
access, reuse state and available mechanics. Activate with `innate <name>
[arguments]`; full multiword names resolve before first-word abbreviations.
The standalone `summon` command also routes through this dispatcher after its
epic-summon handling. The command requires normal standing posture; direct
combat commands retain their own admission checks. A `*` or NULL handler means
“passive” in the UI, not proof that the passive has an effective consumer.
`innate list player` has a historical exclusion list, so it is not the complete
PC-ID census used here.
[Dispatcher](../../../src/classes/innates.c#L4425),
[info](../../../src/classes/innates.c#L1181),
[command registration](../../../src/cmd/interp.c#L3418),
[legacy list filter](../../../src/classes/innates.c#L6556).

### Units, cooldowns, costs and stacking

The engine uses **4 pulses/second**, a base `PULSE_VIOLENCE` of **16 pulses =
4 seconds**, and `PULSES_IN_TICK=300` (**75 seconds**). “Game hours” below are
ordinary affect duration units, decremented at the ordinary affect update;
short affects use pulse durations. Initial update phase can shorten the first
ordinary duration unit. A character's actual attack round also depends on its
combat pulse; “one base round” here always means 4 seconds.
[Clock constants](../../../src/core/config.h#L84),
[ordinary and short updates](../../../src/magic/affects.c#L4114).

Unless stated otherwise, an active handler using `check_innate_time` receives
**one use and a 720-second rest**. Its first use starts a timer; subsequent uses
consume the configured allowance inside that window, and **all uses return at
the first timer's expiry**, rather than one recharge per use. Configuration keys
are `innate.uses.<camelCaseName>` and `innate.timer.secs.<camelCaseName>`; underscores
in names remain underscores. No `innate.uses.*` overrides are committed. Some
handlers supply a fixed rest, while others never call this timer at all.
Cooldowns are per innate ID, not one shared racial pool. The PvP comment in the
timer does not implement a second PvP/non-PvP timer.
[Timer](../../../src/classes/innates.c#L1070),
[committed settings](../../../lib/duris.properties#L2029).

Innate spell wrappers call the spell function directly, usually at character
level. They do not automatically pay memorized slots, PSP, learned-spell mana,
ordinary cast time, or an ordinary casting success roll. Their explicit lag,
rest, vitality cost and the called spell's checks still apply. Invalid attempts
sometimes spend the use **before** a target, terrain or existing-buff rejection;
those cases are listed below. “No rest” never means “no command lag.”

Boolean effects obtained from race, gear and spells do not multiply merely
because all three provide the same bit. Recalculation reasserts passive innate
bits; temporary active buffs remain normal affects with their own stacking and
expiry rules. The same name can hide different mechanics: innate Strength is
+7 MAX STR, while the ordinary spell need not use that value; Duergar
Invisibility is active and terrain-limited, not the separate passive
`INNATE_INVISIBILITY` used by air elementals.
[Passive reconstruction](../../../src/magic/affects.c#L740),
[login setup](../../../src/account/nanny.c#L3981),
[mobile loading](../../../src/core/files.c#L2335).

### Damage and probability notation

`L` is current level, integer division truncates, and `I(x)` is `STAT_INDEX(x)`.
A roll `number(a,b)` includes both endpoints: 1..101 gives a 1/101 outcome, not
1%. Quoted damage is before its downstream defenses unless explicitly called
final. `spell_damage`, `melee_damage`, and raw damage are distinct paths.
“Increased” modifiers add within their category; “More” modifiers combine through
the damage-modifier machinery, and several changes inside one predicate may add
before multiplication. A racial +10% base spell modifier is not necessarily 10%
more final damage after every other modifier.
[Damage pipeline](../../../src/combat/dam_mods.c),
[damage entry points](../../../src/combat/fight.c#L4395),
[stat save](../../../src/core/utility.c#L3247).

## 2. Complete race-by-race unlock roster

`A` means an active handler; `P` means a passive/NULL handler. The number is the
unlock level. Ordinary creation currently enables 21 races; the other 16 require
the restricted-race policy/administrative route. This is availability, not a
statement that a restricted race is balanced for ordinary creation. Every grant
below is taken from active, uncommented assignments, including grants placed far
from the race's main block.

| ID | PC race | Creation | Complete racial grants (`A/P`, level) |
|---|---|---|---|
| 1 | Human | Ordinary | seadog P1 |
| 2 | Barbarian | Ordinary | doorbash A1; bodyslam A1; groundfighting P21; dauntless P41; protection from cold P31 |
| 3 | Drow Elf | Ordinary | levitate A11; faerie fire A1; ultravision P1; globe of darkness A26; magic resistance P1; vulnerable to sun P1; longsword master P11 |
| 4 | Grey Elf | Ordinary | infravision P1; outdoor sneak P21; forest sight P11; magic resistance P1; longsword master P11 |
| 5 | Mountain Dwarf | Ordinary | strength A1; infravision P1; hammer master P31; axe master P11; hatred P21; magical reduction P1; giant avoidance P1 |
| 6 | Duergar Dwarf | Ordinary | invisibility A1; strength A6; ultravision P1; ud-sneak P31; enlarge A26; battle frenzy P16; battlerage A31; vulnerable to sun P1; magical reduction P1 |
| 7 | Halfling | Ordinary | burrow A1; perception P11; quick thinker P1; gamblers luck P26 |
| 8 | Gnome | Ordinary | infravision P1; ultravision P1; farsee P21; reflection A31 |
| 9 | Ogre | Ordinary | doorbash A1; ultravision P1; bodyslam A1; ogre roar A11; vulnerable to sun P1; magic vulnerability P1 |
| 10 | Troll | Ordinary | doorbash A1; ultravision P1; bodyslam A1; regeneration P1; troll skin P21; vulnerable to fire P1; vulnerable to sun P1; swamp sneak P11 |
| 11 | Half-Elf | Restricted | infravision P1; magic resistance P1; quick thinker P30; longsword master P11 |
| 12 | Illithid | Restricted | levitate A1; ultravision P1; blast A1; shift_astral A1; shift_prime A1; magic resistance P1; vulnerable to sun P1 |
| 13 | Orc | Ordinary | summon horde A11; ultravision P1; dayvision P1; summon warg A16; seadog P1 |
| 14 | Thri-Kreen | Ordinary | ultravision P1; bite A11; leap P21; dayvision P1; vulnerable to cold P1 |
| 15 | Centaur | Ordinary | horse body P1; doorkick A1; stampede A21; two-handed sword mastery P31 |
| 16 | Githyanki | Ordinary | levitate A11; ultravision P1; shift_astral A1; shift_prime A1; magic resistance P1; vulnerable to sun P1 |
| 17 | Minotaur | Ordinary | doorbash A1; ultravision P1; charge A11; dayvision P1 |
| 18 | Shade | Restricted | darkness A1; ultravision P1; shade movement A21; vulnerable to fire P1 |
| 19 | Revenant | Restricted | doorbash A1; ultravision P1; bodyslam A1; regeneration P1; shadow door A25; vulnerable to fire P1 |
| 20 | Goblin | Ordinary | ultravision P1; disappear A31; summon totem A26 |
| 21 | Lich | Restricted | ultravision P1; spell absorb P21; eyeless P1; magic resistance P1; vulnerable to sun P1; protection from cold P1; undead fealty P1; call of the grave A1 |
| 22 | Vampire | Restricted | ultravision P1; vampiric touch P1; bite A1; magic resistance P1; vulnerable to sun P1; sacrilegious power P46 |
| 23 | Death Knight | Restricted | ultravision P1; fireshield A31; firestorm A26; protection from fire P1; vulnerable to sun P1 |
| 24 | Shadow Beast | Restricted | strength A1; ultravision P1; ud-sneak P1; enlarge A1; project image A1; vulnerable to fire P1 |
| 25 | Storm Giant | Restricted | **None** |
| 26 | Wight | Restricted | doorbash A1; ultravision P1; bodyslam A1; stone skin A25; vulnerable to fire P1 |
| 27 | Phantom | Restricted | ultravision P1; shift_astral A1; shift_prime A1; fly P21; phantasmal form A20; vulnerable to fire P1; magic resistance P1 |
| 28 | Harpy | Restricted | ultravision P1; fly P1; dayvision P1; perception P1 |
| 29 | Orog | Restricted | ultravision P1; vulnerable to sun P1; warcallers fury P21 |
| 30 | Githzerai | Ordinary | levitate A11; ultravision P1; shift_astral A45; shift_prime A1; dayvision P1; magic resistance P1; spirit of the rrakkma P21 |
| 31 | Drider | Ordinary | ultravision P1; magic resistance P1; groundfighting P21; spider body P1; web_spray A31 |
| 32 | Kobold | Ordinary | ultravision P1; ud-sneak P1; dayvision P1; reflection A31 |
| 33 | Planetbound Illithid | Restricted | levitate A10; ultravision P1; shift_astral A1; shift_prime A1; magic resistance P1; dayblind P1; vulnerable to sun P1 |
| 34 | Kuo Toa | Restricted | ultravision P1; waterbreath P15; throw lightning A30; vulnerable to sun P1; swamp sneak P1 |
| 35 | Wood Elf | Restricted | outdoor sneak P11; forest sight P11; magic resistance P1; longsword master P11 |
| 36 | Firbolg | Ordinary | doorbash A1; bodyslam A1; forest sight P1; magic vulnerability P1 |
| 37 | Tiefling | Ordinary | infravision P1; ultravision P1; protection from fire P1; magic resistance P1 |

Important roster distinctions:

- **Storm Giant has no assigned innate**, although old commented assignments
  mention infravision, doorbash and lightning. Its other racial mechanics still
  exist.
- **Orc has Summon Warg at 16; Goblin does not.** The active Orc assignment is
  physically inside the Goblin block. Goblin has Summon Totem instead.
- **Thri-Kreen Leap is listed at 21, but actual avoidance is race-based at any
  level; Harpy receives that avoidance without a Leap table entry.**
- **Troll no longer has Groundfighting.** Barbarian and Drider receive it at 21.
- Gnome and Kobold gain **Reflection at 31**. This summons combat images; it is
  not a spell-reflection shield.
- Original Illithid and Planetbound Illithid are distinct PC IDs. The former
  receives Blast and level-1 Levitate, the latter Dayblind and level-10 Levitate.
- PC Vampire is `RACE_PVAMPIRE`, distinct from the NPC `RACE_VAMPIRE`. The NPC
  receives Gaze; the PC does not. Neither current Vampire assignment grants fire
  vulnerability. Lich's old fire vulnerability is also commented out.
- Halfling's old Barter, Calming and Flurry grants, Drider Webwrap, Drow Darkness,
  Fireball and Mass Dispel, and dwarf/gnome Miner grants are inactive comments.
  Existing handlers or help names do not grant them.

## 3. Senses, information and concealment

### Infravision and Ultravision

`INNATE_INFRAVISION` sets `AFF_INFRAVISION`; `INNATE_ULTRAVISION` sets
`AFF2_ULTRAVISION`. They affect room/object/character visibility, directional
looking, names shown to observers, map range and the ability to acquire visible
targets. Neither is detect invisibility, sense life, or see hidden. Existing
blindness and concealment checks remain separate.

Ultravision selects the time-dependent night-vision map curve on the surface;
underdark maps start at range **6** instead of **4**. Infravision normally adds
**1** to the surface/underdark range, with a surface cap of 8 before later
adjustments. Underdark vision from another effect takes precedence over that
extra infravision point. Normal indoor/zone map range starts at 5. Forest caps,
perception, ocean range and altitude are applied later.
[Bits](../../../src/magic/affects.c#L750),
[map calculation](../../../src/world/map.c#L1221),
[visibility](../../../src/core/utility.c#L1780),
[directional looking](../../../src/cmd/actinf.c#L2729).

The current visibility implementation retains partially disabled pre-2016
day/night-blind logic. Several missing-vision branches no longer reject every
target; without infra they still reject `INFRA_INVIS_RACE` targets. Infravision
does not justify claiming a universal “red silhouettes only” restriction from
old comments/help. Assess object sight, character sight and map range separately.
Tiefling and Gnome have both sight innates; Grey Elf, Mountain Dwarf and Half-Elf
have infra alone; Wood Elf and Firbolg have neither racial sight bit. Those are
real differences even where gear can supply the missing bit.
[Current character path](../../../src/core/utility.c#L1791),
[object sight](../../../src/core/utility.c#L1987),
[name display](../../../src/core/utility.c#L3432).

### Dayvision and Dayblind

`INNATE_DAYVISION` has **no active consumer** beyond assignment and presentation.
It is not an additional daylight save, sunlight immunity or damage reduction.
The races listing it avoid Dayblind chiefly because they are not granted
`INNATE_DAYBLIND`, rather than because Dayvision actively cancels it.

`INNATE_DAYBLIND` is actually granted to **Planetbound Illithid** among the PC
IDs. The other historical evil-race grants are commented out. The predicate
exempts eyeless characters, trusted staff, twilight rooms and a globe on the
viewer. Map sight on a sunlit surface uses the time-dependent dayblind curve,
with +2 for infra/ophidian eyes, bounded 0..8; underdark maps use 8 before later
bonuses/caps. Directional looking can reject a bright destination without
infravision, and room visibility considers another occupant's darkness globe.
Current character sight has the legacy exceptions described above; Dayblind is
not identical to `AFF_BLIND` and `IS_BLIND` does not include it.
[Predicate](../../../src/core/utils.h#L1217),
[map branch](../../../src/world/map.c#L1245),
[bright destination](../../../src/cmd/actinf.c#L2841),
[roster](../../../src/classes/innates.c#L614).

### Eyeless — `INNATE_EYELESS`

PC Lich has Eyeless. It sets `AFF5_NOBLIND`, blocks the common `blind()` routine
and explicit power-word-blind, dirt-toss, gaze and dazzling/eye-dependent attack
branches. It also bypasses the Dayblind predicate, supplies a fixed map range
of **8** before the early return (so later forest/perception/altitude adjustments
are skipped), and allows certain combat perception checks without normal sight.
It is a set of explicit exemptions, not permission to ignore all invisibility,
hidden-target, targeting or room rules.
[Map and light](../../../src/world/map.c#L1209),
[blindness](../../../src/magic/affects.c#L3516),
[power word](../../../src/magic/magic.c#L20476),
[gaze](../../../src/cmd/actoff.c#L13186),
[dirt](../../../src/cmd/actnew.c#L2951),
[combat perception](../../../src/combat/fight.c#L11440).

One common combat-defense eligibility condition actually reads the attacking
`ch`'s Eyeless state while checking whether the opponent can defend. That
subject choice can let an opponent reach its defense checks without seeing
an eyeless attacker; it should not be described as universally improving the
eyeless defender's own sight.

### Farsee, Forest Sight and Perception

- **Farsee — `INNATE_FARSEE`:** Gnome at 21 receives the farsee bit. It enables
  detailed looking into adjacent rooms, subject to doors, reciprocal line of
  sight, room sight blocks and light checks. It improves the improved-track roll
  by **10** if that skill is available. Farsee does not train tracking or reveal
  every concealed creature. Goblin's worn totem can provide this bit from 31.
  [Look](../../../src/cmd/actinf.c#L2729),
  [tracking](../../../src/cmd/track.c#L719).
- **Forest Sight — `INNATE_FOREST_SIGHT`:** Firbolg at 1, Grey/Wood Elf at 11
  avoid the normal **range-3 forest map cap**. It preserves whatever their
  otherwise calculated range is; it does not itself set range 8 or provide night
  vision. Druid/Blighter class ownership can duplicate this benefit. The separate
  temporary `AFF5_FOREST_SIGHT` branch sets range 5 and can still change the final
  result. [Map ordering](../../../src/world/map.c#L1317).
- **Perception — `INNATE_PERCEPTION`:** Harpy at 1 and Halfling at 11 add **1**
  map range and **30** to improved-track skill before the tracking contest.
  Without that skill, the missing-skill sentinel remains effectively unusable.
  It does **not** grant a hitroll bonus, hawkvision or see-hidden. Ocean maps
  subsequently use range 10 regardless of this +1; eyeless returns earlier.
  [Map](../../../src/world/map.c#L1327),
  [tracking](../../../src/cmd/track.c#L714),
  [explicit no-hitroll comment](../../../src/magic/affects.c#L798).

### Terrain sneaking

All three feed `SNEAK(ch)`, alongside the ordinary sneak bit. That predicate
controls movement arrival/departure announcements and some movement-triggered
aggression behavior. These are automatic terrain conditions with no learned
sneak roll, activation, timer or per-use cost. They suppress eligible movement
messages; they do **not** make the creature invisible while standing in a room.
Mount, light/object visibility, room/command and observer paths still matter.
Sense Life/skill-awareness observers can detect the silent entry through the
movement path's INT save; innate sneak is not proof that everyone misses it.
For the command-end aggression gate, moving while sneaking still has a **1/20**
failure branch; remaining in the same room does not receive that movement
exemption. Other Calming/CHA and aggression rules follow afterward.
[Shared predicate](../../../src/core/defines.h#L1385),
[movement messages](../../../src/cmd/actmove.c#L1151),
[entry announcements](../../../src/cmd/actmove.c#L1706),
[command aggression](../../../src/cmd/interp.c#L2518).

- `INNATE_OUTDOOR_SNEAK`: Grey Elf at 21 and Wood Elf at 11; only sector IDs
  **2..4: field, forest, hills**. “Outdoor” does not mean every outdoor sector,
  every road, mountain, swamp or water tile.
- `INNATE_UD_SNEAK`: Duergar at 31, Kobold/Shadow Beast at 1; only
  `IS_UNDERWORLD(room)`. This is not a blanket exemption in every dark room.
- `INNATE_SWAMP_SNEAK`: Kuo Toa at 1 and Troll at 11; swamp or underworld slime
  terrain. In those terrains it additionally removes their map occupant marker
  from ordinary observers. Separately, **possession of the innate** satisfies
  the boat-admission check, without testing swamp terrain in that branch. This
  is wider than the stealth terrain restriction and does not grant waterbreath.
  [Terrain macros](../../../src/core/utils.h#L172),
  [map suppression](../../../src/world/map.c#L703),
  [boat admission](../../../src/cmd/actmove.c#L958).

### Burrow — `INNATE_HIDE`

Halfling at 1 directly sets `AFF_HIDE`, with **4s lag**, default 720s rest, no
skill roll and no actual digging, room relocation or subterranean travel.
Already hidden rejects before spending a use. The handler imposes no ground,
soil or outdoor requirement. Common hide detection, sense-life interaction,
attacking/command reveal and ordinary movement reveal still apply. This is
reliable access to the hidden state, not permanent invisibility.
[Handler](../../../src/classes/innates.c#L3051),
[hidden-target sight](../../../src/core/utility.c#L1765),
[command reveal](../../../src/cmd/interp.c#L2282).

### Disappear — `INNATE_DISAPPEAR`

Goblin at 31 directly hides with **4s lag and no reuse timer** if anyone in the
room is fighting. The Goblin need not itself be engaged. It does not stop combat,
erase an opponent's target, move rooms or supply sneak. The normal hidden-state
consumers decide how useful hiding is against existing attackers and observers.
[Handler](../../../src/classes/innates.c#L1367).

### Underdark Invisibility — `INNATE_UD_INVISIBILITY`

Duergar at 1 can self-apply ordinary `SPELL_INVISIBILITY`/`AFF_INVISIBLE` for
**45 game hours**, with default rest and **no explicit handler lag**. Already
invisible returns before the timer; being outside `IS_UD_MAP` and
`IS_UNDERWORLD` rejects **after spending a use**. Once applied, this handler does
not require remaining underground. Ordinary detection, faerie fire, attacks,
revealing commands and affect removal/recalculation apply; it grants no extra
invisibility tier. [Handler](../../../src/classes/innates.c#L2676),
[visibility checks](../../../src/core/utility.c#L1710).

### Shade Movement — `INNATE_SHADE_MOVEMENT`

Shade at 21 receives an ordinary affect lasting `1+L/10` game hours and direct
hide/sneak bits. Default rest; no explicit handler lag. Starting in full sun
outside twilight or while already affected rejects before the timer. It allows
walking while hidden through dark rooms. Entering sunlight **or twilight**
removes shade movement/hide; the command interpreter also breaks it for commands
outside its allowed hidden-command and movement rules. Looking/listening,
glancing, reading, stealing and scanning have common hide exceptions, so “any
other command ends it” is an oversimplification. This is concealment, not
teleportation, passdoor or immunity to detection.
[Activation](../../../src/classes/innates.c#L3408),
[destination check](../../../src/cmd/actmove.c#L1936),
[command exceptions](../../../src/cmd/interp.c#L2282).

## 4. Flight, breathing, bodies and physical access

### Fly — `INNATE_FLY` and Levitate — `INNATE_LEVITATE`

Harpy has passive Fly at 1; Phantom at 21. It continuously supplies `AFF_FLY`.
Levitate is an active self-cast on Drow/Githyanki/Githzerai at 11, Planetbound
Illithid at 10, and original Illithid at 1. It lasts `max(L,10)` game hours,
uses default rest and **4s lag even when already floating or resting**. Existing
levitate rejects before spending a use. Fly and Levitate share many protections
but are not interchangeable:

- Both avoid ordinary falling admission and provide the flight/float exemptions
  for no-ground, water/boat and footing checks. A mount's flight/float state can
  be the relevant state for its rider. Losing the effect over empty space can
  expose the character to falling again.
- Air-plane **horizontal travel requires Fly**; Levitate permits the up/down
  branch, not unrestricted lateral flight. Other movement checks separately
  handle entering/leaving no-ground rooms and carried/ridden participants.
- Fly lowers eligible travel cost to 1 on inside/city/road sectors or 2 elsewhere;
  Levitate does so on up/down movement. Mountain/ocean exceptions and the normal
  burden, altitude and freedom-of-movement pipeline remain.
- Both add **+1 AGI stat-save score**, before the save clamp, and affect footing
  for physical skills/currents. This is not an unconditional dodge percentage.
- Fly adds **+1 surface map range** after its initial 0..8 calculation and affects
  airborne/altitude movement and sight. Levitate does not add that map point.
- Their presence influences fall/knockdown/trap checks that explicitly inspect
  the bits; neither makes all forced movement or control effects impossible.

[Passive bit](../../../src/magic/affects.c#L760),
[Levitate](../../../src/classes/innates.c#L1796),
[movement admission](../../../src/cmd/actmove.c#L308),
[travel cost](../../../src/core/utility.c#L2628),
[falling](../../../src/world/falling.c#L158),
[AGI save](../../../src/core/utility.c#L3302),
[map](../../../src/world/map.c#L1276).
The [size reference](race-size.md) details the shared physical and falling paths.

### Waterbreath — `INNATE_WATERBREATH`

Kuo Toa at 15 continuously receives `AFF_WATERBREATH`. It prevents the underwater
breath-holding/drowning event from starting and clears breath/drowning bits when
an existing event sees it. Otherwise that path moves from breath-holding to
3-HP drowning losses and eventual death. It also makes waterbreath spell
application redundant. It is **not** a boat, flight, swimming skill, current
immunity, water-walking or permission to cast every spell underwater. HP recovery
can still be stopped by swimming; the breathing/drowning recovery blockers are
avoided only when their state is cleared.
[Underwater events](../../../src/mob/specials.c#L108),
[bit](../../../src/magic/affects.c#L756),
[HP recovery blockers](../../../src/world/limits.c#L426).

### Horse Body and Spider Body

`INNATE_HORSE_BODY` belongs to Centaur at 1; `INNATE_SPIDER_BODY` to Drider at 1.
They are permanent body predicates, with both benefits and restrictions:

- Both prevent ordinary mounting by the character and completely reject the
  body-specific **groundslam** branch against them.
- Native Centaur/Drider PCs can themselves carry an eligible consenting PC
  with a saddle in the appropriate body slot, subject to the mount command's
  race/size/room/rider checks. This uses native race predicates in addition to
  the body-slot rules; merely acquiring a body innate is not a universal
  player-mount capability.
- Bash, tackle, maul and trip generally require the attacker to be **strictly
  larger** than the horse/spider-bodied target. Springleap needs at least equal
  size for this body check, then its own general size window. AI eligibility
  predicates do not all have identical checks: `isBashable` explicitly checks
  horse body, while actual bash checks both. These are per-action restrictions,
  not a universal resistance to bodyslam, stampede, stun or paralysis.
- Body-specific armor slots become available: horse-body or spider-body.
  Spider abdomen wear explicitly checks the innate. Native race restrictions
  on legs/feet/hands are additional rules; these innates alone do not remove all
  humanoid torso equipment or grant all quadruped slots.
- Movement text changes to trotting/skittering where that message branch wins.
- Horse Body redirects the ordinary **Kick** command to **Rearkick** and
  authorizes Rearkick directly. Spider Body does not.

[Mount](../../../src/classes/mount.c#L306),
[groundslam](../../../src/combat/grapple.c#L1499),
[bash](../../../src/cmd/actoff.c#L8637),
[tackle](../../../src/cmd/actoff.c#L9266),
[maul](../../../src/cmd/actoff.c#L10297),
[springleap](../../../src/cmd/actoff.c#L12000),
[trip](../../../src/cmd/actoff.c#L12405),
[slots](../../../src/cmd/actinf.c#L8655),
[spider armor](../../../src/cmd/actobj.c#L6934),
[Kick routing](../../../src/cmd/actoff.c#L5780).

Rearkick uses normal kick admission/chance and can be guarded. It requires the
front line, fails to hurt immaterial targets, and gives **8s actor lag**.
Base damage is random half..full of `max(STR/2,kickRating*configuredDamage)`,
then 0.75x against targets over one size larger or 1.25x against targets over one
size smaller, through melee damage/touch-vamp defenses. A standing target at
least two sizes smaller can additionally be kicked into a neighboring room and
made prone, subject to takedown and forced-movement admission. This grants an
attack route; it does not grant a learned Kick rating or guarantee a roomkick.
[Rearkick](../../../src/cmd/actoff.c#L10946).

## 5. Defense, saves, recovery and vulnerabilities

### Magic Resistance — `INNATE_MAGIC_RESISTANCE`

The innate enables **spell shrug checks**. Its racial property is a base rating,
not an always-on final percentage. At ordinary PC levels:

```text
R = configured innate.shrug.<race>
r = max(5, int((R - min(6,56-L)) * min(1,L/50.0)))
add eligible Rrakkma bonus, then cap at 100
shrug if number(1,101) <= r
```

Thus rating 38 means 38/101, about 37.62%, at 56 before penetration. At 50 the
same Drow has rating 32; at 30 rating 19; at 1 the floor is 5. The 5 minimum is
only useful when a caller actually checks Magic Resistance. A race with no
innate does not gain a universal 5/101 shrug because the helper returns 5.
Racial lookup uses the mechanics race, while ownership can use the shape race.
[Calculation](../../../src/classes/innates.c#L4904),
[check](../../../src/classes/innates.c#L4990),
[configured values](../../../lib/duris.properties#L1968).

| PC holders | Committed base rating at 56 | Raw shrug chance at 56 |
|---|---|---|
| Illithid | 70 | 70/101 = 69.31% |
| Lich | 65 | 65/101 = 64.36% |
| Planetbound Illithid | 50 | 50/101 = 49.50% |
| Vampire (PC `PVampire` key) | 40 | 40/101 = 39.60% |
| Drow Elf | 38 | 38/101 = 37.62% |
| Grey Elf | 30 | 30/101 = 29.70% |
| Githyanki; Drider | 25 | 25/101 = 24.75% |
| Half-Elf; Phantom; Githzerai; Tiefling | 20 | 20/101 = 19.80% |
| Wood Elf | 5 | 5/101 = 4.95% |

Self-casts and a caster consent-linked to the target bypass shrug. Trusted
casters bypass it against mortal targets. Otherwise it is checked by each
spell's implementation, including potentially helpful spells; no blanket
“offensive-only” test exists in `resists_spell`. `SPLDAM_NOSHRUG`, physical
poison, and handlers that never invoke the shrug path bypass it. A negative
energy barrier and various earlier defenses can resolve damage before shrug.

Desecrated land subtracts **10 rating** at the shrug test, after the helper's
minimum; low shrug can therefore become ineffective there. A caster with spell
penetration can defeat a successful shrug with a roll on **0..110** below
`clamp(10,skill/2,60)` for ordinary PCs, requiring the same room. Qualifying
non-pet NPCs use level in that branch. The penetration marker makes subsequent
checks pass until consumed/expired and also causes a separate damage reduction
on the next spell-damage predicate; shrug chance alone cannot describe final
spell damage. AI also considers shrug when choosing magical targets.
[Consent and penetration](../../../src/classes/innates.c#L5010),
[spell-damage ordering](../../../src/combat/fight.c#L4740),
[penetration damage](../../../src/combat/dam_mods.c#L757),
[AI selection](../../../src/mob/mobact.c#L209).

### Magical Reduction — `MAGICAL_REDUCTION`

Mountain Dwarf and Duergar at 1 take a **0.80 multiplier on generic
(`SPLDAM_GENERIC`) spell damage** in its modifier predicate. It does not grant
shrug or reduce every magical element. Fire/cold/lightning/holy/etc. damage is
outside this predicate. The distinction favors dwarves against generic nukes,
while an elf's shrug can prevent qualifying status spells as well as damage.
[Predicate and value](../../../src/combat/dam_mods.c#L85),
[generic gate](../../../src/combat/dam_mods.c#L348).

### Magic Vulnerability — `MAGIC_VULNERABILITY`

Ogre and Firbolg at 1 receive **+0.10 in the Increased category of incoming
spell damage**. It applies across spell-damage types when that pipeline reaches
the modifier, not only generic spells. The predicate explicitly requires those
native race IDs even if another shape grants ownership. It neither makes a
status spell more accurate nor subtracts a saving-throw rating. Other Increased
modifiers add before More multipliers; it is not always 1.10x final damage.
[Value](../../../src/combat/dam_mods.c#L98),
[native-race gate](../../../src/combat/dam_mods.c#L631).

### Protection from Fire and Protection from Cold

`INNATE_PROT_FIRE` belongs to Tiefling and Death Knight at 1;
`INNATE_PROT_COLD` to Lich at 1 and Barbarian at 31. Recalculation sets the
respective protection bits. With the committed `damage.reduction.protElement`
value, the normal elemental predicate contributes **-15%**, giving 85% of that
element's damage when isolated. A same-element elemental shield replaces this
protection reduction with its own reduction; obtaining both does not double it.
Opposite shields and other elemental modifiers still apply. Protection is not
shrug, a save bonus, elemental immunity or protection against all environmental
sources labeled “fire” or “cold.”

The wall implementations have additional explicit benefits: fire protection
leaves **one third** of a wall-of-flames burn; cold protection leaves roughly
**two thirds** of wall-of-ice damage, with integer rounding. These are separate
wall formulas, not the ordinary 15% spell reduction.
[Bits](../../../src/magic/affects.c#L778),
[damage facts](../../../src/combat/dam_mods.c#L161),
[fire predicate](../../../src/combat/dam_mods.c#L410),
[cold predicate](../../../src/combat/dam_mods.c#L475),
[walls](../../../src/magic/spells.c#L1005),
[properties](../../../lib/duris.properties#L187).

### Vulnerable to Fire — `INNATE_VULN_FIRE`

Troll, Shade, Revenant, Shadow Beast, Wight and Phantom at 1 receive **+30% fire
spell damage** in the fire predicate (`DF_VULNFIRE=1.30`). In that same predicate,
a fireshield or fire protection contributes **-10%** instead of the normal
non-vulnerable shield/protection reduction. Isolated totals are therefore
1.30x unprotected and 1.20x with either of those protections, before the other
fire predicates and downstream defenses. These two protections are mutually
exclusive branches, not two -10% reductions.

This path also creates/refreshes a **30-second `TAG_TROLL_BURN`** on every
fire-vulnerable target. Its regeneration consequence specifically checks native
Troll: **innate regeneration becomes 1 before posture multipliers**, rather
than `10*L`. It does not become `L`, and other HP-recovery components are not all
set to 1. Non-Troll holders receive the tag without the Troll race branch.
Repeated fire can maintain suppression. The refresh writes the existing
duration field; short-affect expiry is event-driven, so that write alone should
not be assumed to reschedule an already-running event.
[Fire predicate](../../../src/combat/dam_mods.c#L377),
[burn duration](../../../src/combat/dam_mods.c#L111),
[Troll regeneration](../../../src/classes/innates.c#L4856),
[short expiry](../../../src/magic/affects.c#L2079).

### Vulnerable to Cold — `INNATE_VULN_COLD`

Thri-Kreen at 1 receives **+35% of base cold spell damage** in the Increased
category, and each qualifying cold-damage invocation tests
`NewSaves(SAVING_PARA,+2)`. Failure adds a **60-pulse = 15-second Slow** short
affect. This is both damage vulnerability and a throughput/control penalty;
Slow affects attacks, casting and other haste/slow consumers. The +2 is a
harder magical save (+10 in its threshold calculation), not two percent.
Cold protection can mitigate damage but is not checked as immunity to this
extra Slow. The predicate creates another affect rather than explicitly
coalescing an existing Slow.
[Values](../../../src/combat/dam_mods.c#L206),
[predicate](../../../src/combat/dam_mods.c#L731),
[save modifiers](../../../src/net/sparser.c#L1277).

### Vulnerable to Sun — `INNATE_VULN_SUN`

Drow, Duergar, Ogre, Troll, original/Planetbound Illithid, Githyanki, Lich,
Vampire, Death Knight, Orog and Kuo Toa have this at 1. It has **three separate
effects with different exemptions**:

1. The generic character sweep visits each character every **20 seconds** and
   calls the sunlight damage check outside Bloodlust day. Direct sunlight
   removes **5..20 HP**, floored at 1. NPCs/staff, twilight, forest, swamp and
   the character's darkness globe avoid this check. It never directly kills.
2. HP regeneration is zero in sun outside twilight/globe, **unless the room is
   magically dark**. Forest/swamp and Bloodlust are not explicit exemptions in
   this recovery predicate; their result depends on `IS_SUNLIT`/room state.
3. Mana/PSP regeneration is zero in sun outside twilight/globe. This predicate
   has **no magic-dark exception**. Merely avoiding the 5..20 HP burn is not
   proof that either resource is recovering.

Sun vulnerability is independent of Dayblind. Most of its holders have no
active Dayblind grant. Drow's level-26 globe provides a personal mitigation
tool, but it has its own duration, rest and mage-flame conflict.
[Burn sweep](../../../src/world/handler.c#L255),
[burn gates](../../../src/world/handler.c#L463),
[mana](../../../src/world/limits.c#L156),
[HP](../../../src/world/limits.c#L418).

A separate `event_sundamage` implementation has 1..8 damage with racial
multipliers and a five-pulse recurrence. No active external scheduling caller
was found in this checkout (its nearby start call is commented); it is not
added on top of the active 20-second burn in this comparison.
[Legacy event](../../../src/world/handler.c#L517).

### Regeneration — `INNATE_REGENERATION`

Troll and Revenant have it at 1. It reasserts the regeneration bit and adds an
innate HP-recovery component. With no class/terrain bonuses and no burn:

```text
Troll:    L * (1 + 9) = 10L awake, 20L resting, 30L sleeping
Revenant: L * (1 + 4) =  5L awake, 10L resting, 15L sleeping
```

At 56 that is **560/1120/1680** versus **280/560/840** HP per game tick before
the rest of HP regeneration, combat and room/difficulty modifiers. Recovery
events accrue a per-tick rate over elapsed pulses; these are not instant heals
on every attack or every real second. Burned Troll's component is **1/2/3**
instead. Troll/Revenant race branches replace the ordinary regeneration-spell
multiplier selection, so casting that spell does not simply add the configured
spell amount to their native multiplier. Huntsman forest, Water Magus and
terrain-attunement additions still follow the helper's own ordering/truncation.

In combat, a real affect carrying the regeneration bit lets the current
recovery calculation retain its normal combat branch; a passive bit alone
halves the **whole gain**. No-heal rooms, building, swimming/drowning and
sunlight can suppress recovery. This is why Troll's large paper rate is not
unconditional sustained combat healing.
[Helper](../../../src/classes/innates.c#L4861),
[properties](../../../lib/duris.properties#L2703),
[HP aggregation and combat](../../../src/world/limits.c#L351),
[elapsed-pulse accrual](../../../src/world/events.c#L223).

### Troll Skin — `INNATE_TROLL_SKIN`

Troll at 21 takes **85%** of the melee damage reaching the skin multiplier.
It stacks within the melee sequence with armor and other applicable reductions.
`PHSDAM_NOREDUCE` bypasses it. It is not 15% immunity to spell/raw damage and is
independent of Regeneration; fire weakness does not directly switch Troll Skin
off. [Melee application](../../../src/combat/fight.c#L5486),
[setting](../../../lib/duris.properties#L178).

### Groundfighting — `INNATE_GROUNDFIGHTING`

Barbarian and Drider at 21 retain their normal attack count when down, avoid the
ordinary kneeling/sitting/prone incoming melee multipliers, and can dodge while
down at **half** the computed dodge percentage. Ordinary characters lose about
one third of attacks when kneeling and half when sitting/prone; integer attack
counts matter. Without this innate, the ordinary dodge branch rejects a downed
character entirely. Mounted sidestep is evaluated earlier and other status
penalties, gaze, stun, blindness, restraints and command posture requirements
still apply. It does not keep the character standing, remove lag or cancel stun.
[Attack count](../../../src/combat/fight.c#L10954),
[damage posture](../../../src/combat/fight.c#L5552),
[dodge admission](../../../src/combat/fight.c#L9345),
[half dodge](../../../src/combat/fight.c#L9398).

### Giant Avoidance — `INNATE_GIANT_AVOIDANCE`

Mountain Dwarf at 1 multiplies its initial dodge score by **1.10** against the
explicit attacker IDs **Troll, Ogre or generic Giant**. This happens after
subtracting weapon skill but before level/stat additions, floors, caps and
status modifiers. It is not a flat +10% dodge chance, does not create a second
dodge roll, and the explicit list does not include every race with “giant” in
its name (e.g. Storm Giant/Snow Ogre). If the pre-multiplied score is negative,
the multiplication makes that component more negative.
[Consumer](../../../src/combat/fight.c#L9367).

### Dauntless — `INNATE_DAUNTLESS`

Barbarian at 41 continuously receives `AFF4_NOFEAR`. It blocks ordinary fear
immunity checks, frightening-presence style fear, several fear/cower/collapse
branches and Gaze's explicit nofear gate. Force-enabled fear checks and control
mechanics that only use `SAVING_FEAR` are not all immunity checks: a fear-based
stun duration roll is not automatically rejected just because the character is
Dauntless. It neither grants Groundfighting early nor grants general stun or
paralysis immunity.
[Bit](../../../src/magic/affects.c#L806),
[fear immunity and force](../../../src/combat/fight.c#L11684),
[frightening presence](../../../src/classes/dreadlord.c#L88),
[Gaze](../../../src/cmd/actoff.c#L13195),
[Stun implementation](../../../src/magic/affects.c#L3563).

### Quick Thinker — `INNATE_QUICK_THINKING`

Halfling at 1 and Half-Elf at 30 gain three distinct benefits:

- `NewSaves` rerolls a failed magical saving throw **once**. If the original
  success probability is `p`, the result is `1-(1-p)^2`; 50% becomes 75%, and
  20% becomes 36%. This is not a flat +15% and also affects saves against
  nonmagical actions that happen to use `NewSaves`.
- `StatSave` for **INT or POW only** has a **15% immediate pass**, then its
  ordinary save roll. If its ordinary pass chance is `q`, total is
  `0.15+0.85q`. Other stat saves do not receive that extra pass or a reroll.
  The normal capped stat save is 19/21, so the combined capped INT/POW chance
  becomes about **91.90%**, not certainty.
- Combat quaff's success threshold is multiplied by **1.25**, just as Combat
  Mind would do. Having both uses the same OR branch, so they do not multiply
  twice. Other DEX/AGI/Luck inputs, potion timers and special bottle exceptions
  remain; a sufficiently high threshold can remove normal spill failures.

[Magic saves](../../../src/net/sparser.c#L1300),
[stat saves](../../../src/core/utility.c#L3214),
[quaff](../../../src/cmd/actoth.c#L4795).

### Gambler's Luck — `INNATE_GAMBLERS_LUCK`

Halfling at 26 adds **10 final effective Luck** after racial multiplication and
the usual 1..511 clamp. At base 100 this changes Halfling Luck from 120 to 130;
the addition is not multiplied by 1.20 again. Recalculation reapplies rather
than repeatedly accumulating the +10. No second clamp in that block prevents a
geared value of 521.

Every effective-Luck consumer can be affected: takedown and special-attack
contests; ranged damage/critical shot/arrow blocking; bard success/dissonance;
hide, steal, listen, combat quaff and search/dig; loot/material/recipe/rare-item
rolls; enhance, mining, salvage and forage; and item/class proc rolls. Benefits
are often integer thresholds and can already be saturated. Some exceptional
predicates reverse the intuitive benefit (the Barbarian restoration item proc
tests Luck **below** a roll). Current melee shield block does **not** use the
retired, broken Luck/percent branch described in the older stats reference.
For the full consumer inventory and that resolved distinction, see
[stats mechanics](race-stats.md#49-stealth-perception-movement-and-survival)
and [stats issue analysis](race-stats-issues.md).
[Addition](../../../src/magic/affects.c#L1032),
[quaff example](../../../src/cmd/actoth.c#L4788),
[current block](../../../src/combat/fight.c).

### Spell Absorb — `INNATE_SPELL_ABSORB`

Lich at 21 can negate incoming spell damage and refill **one highest spent
spell circle**, if it actually uses the spell-slot resource model. After the
spell has survived shrug and reached this branch, both must pass:

```text
damage/50 > number(0,9)
number(1,100) <= L/2
```

The first probability is `clamp(floor(damage/50),0,10)/10`. At 56 the second
is 28%: 50..99 damage therefore gives **2.8%**, 100..149 **5.6%**, and 500+
**28%**, conditional on reaching this branch. These are not additional chances
on a spell already shrugged. Self damage and `SPLDAM_NOSHRUG` bypass absorb;
full slot pools leave no refill and **do not negate the spell**. Normal book,
PSP or other non-slot builds get no benefit from merely owning the innate.
[Ordering, slots and return](../../../src/combat/fight.c#L4753).

### Undead Fealty — `INNATE_UNDEAD_FEALTY`

Lich at 1 causes aggressive undead NPCs at least **10 levels lower** to pass
over it in the shared aggression predicate, unless they remember it or carry a
CTF tag. At level 56 that protects against eligible undead through 46. It does
not charm/control them, protect allies, stop a current fight or prevent every
scripted attack. Prior predicate conditions and independent content procs can
still matter. [Aggression exemption](../../../src/core/utility.c#L2991).

### Sacrilegious Power — `INNATE_SACRILEGIOUS_POWER`

PC Vampire from 46 receives a holy-damage modifier **only while considered an
undead race**: 75% at 46..50, 50% at 51..55, 25% at 56+. These replace that
predicate's neutral 1.0 holy factor and interact with other holy modifiers;
they are not immunity, generic spell resistance, a healing bonus or an increase
to damage dealt. Its innate grant and undead identity are separate gates.
[Tiers](../../../src/combat/dam_mods.c#L182),
[undead gate](../../../src/combat/dam_mods.c#L552).

## 6. Offensive passives, weapon choices and group scaling

### Weapon masteries

These three innates modify the character's global hitroll/damroll when its
**primary weapon's exact type** matches. A qualifying secondary weapon alone
does not trigger them, nor does every slashing weapon count as a longsword.
Hitroll is capped at 127 and damroll at 255 in these additions. Once added to
character totals, their downstream contribution is not confined to damage from
that one primary weapon.

- **Axe Master — `INNATE_AXE_MASTER`:** Mountain Dwarf at 11; primary
  `WEAPON_AXE`; +`L/8` hitroll and +`L/12` damroll. At 56: **+7/+4**.
- **Hammer Master — `INNATE_HAMMER_MASTER`:** Mountain Dwarf at 31; primary
  `WEAPON_HAMMER`; +`L/8` hitroll and +`L/10` damroll. At 56: **+7/+5**.
  Ragelord class ownership is the same innate, not a second copy.
- **Longsword Master — `INNATE_LONGSWORD_MASTER`:** Drow, Grey Elf, Half-Elf
  and Wood Elf at 11; primary `WEAPON_LONGSWORD`; +`L/8` hitroll and +`L/12`
  damroll. At 56: **+7/+4**.

At level 11 the axe/longsword bonus is only +1 hitroll/+0 damroll; later integer
breakpoints matter. These bonuses do not grant weapon proficiency or another
attack, and their value depends on how hitroll and damroll affect the chosen
attack. [Values](../../../src/magic/affects.c#L575),
[equipment gates](../../../src/magic/affects.c#L1003).

**Two-handed Sword Mastery — `TWO_HANDED_SWORD_MASTERY`:** Centaur at 31
returns **100** for `SKILL_2H_SLASHING` at the start of the effective-skill lookup,
before the ordinary learned-rating path. It is proficiency, not +100 hitroll,
+100 damage, or all two-handed weapon types. It gives even a class without
trained two-handed slashing this effective rating, subject to equipping and
using an eligible weapon and the attack's other rules. The early return also
bypasses later ordinary skill modifiers for this lookup.
[Rating override](../../../src/core/utility.c#L5215).

### Strength — `INNATE_STRENGTH`

Mountain Dwarf at 1, Duergar at 6 and Shadow Beast at 1 apply **+7 MAX STR** for
**5 game hours**, with default rest and **4s successful-use lag**. The timer is
spent before rejecting an existing `SPELL_STRENGTH`. It shares that spell's
affect type, so it cannot simply layer an independent racial +7 on an existing
Strength spell. MAX STR adds both current and maximum unscaled STR, then the
selected racial STR factor applies. At base 100 with native factors, +7 means
**+10 effective STR** for Mountain Dwarf (135%), **+9** for Duergar
(130%), **+8** for Shadow Beast (120%), subject to rounding/caps.

Effective STR changes the strength hit/damage tables, carrying/wielding/burden,
physical attack and escape contests, current/footing checks and strength-based
spell damage tiers. It does not multiply every outgoing attack by 1.07. The
[stats reference](race-stats.md) gives the consumer formulas and breakpoints.
[Handler](../../../src/classes/innates.c#L2716),
[MAX fallthrough](../../../src/magic/affects.c#L1204),
[effective STR](../../../src/magic/affects.c#L833).

### Enlarge — `INNATE_ENLARGE`

Duergar at 26 and Shadow Beast at 1 self-apply the enlarge bit for **5 game
hours**, default rest, **4s lag**. It adds one size through the shared size
pipeline, subject to its limits and form rules. Existing enlarge/titan form
spends a use without another increase. It does not directly add STR or HP.

The size change alters legal target windows and chance/damage branches of
bash, bodyslam, tackle, trip, maul, springleap, charge, roomkick, grapple and
related skills; body stability and mount capacity; some weapon/equipment
admission; and physical mass/terrain interactions. Larger can be harmful:
some targets become too small for bodyslam or charge, and different consumers
read stored versus effective size. The comprehensive per-consumer rules and
the six native mapping inconsistencies are in [race-size.md](race-size.md)
and [race-size-issues.md](race-size-issues.md).
[Handler](../../../src/classes/innates.c#L2794),
[size application](../../../src/magic/affects.c).

### Battle Frenzy — `INNATE_BATTLE_FRENZY`

Duergar at 16 has a **1/21** proc at the relevant ordinary hit-processing point
against a **humanoid** target. Its follow-up still needs a to-hit check using
unarmed-damage skill, rather than automatically landing because the main hit
did. Extra base damage is `damroll*L*number(1,2)/40`, then normal melee defenses
and touch-vamp processing. It is not a universal 1/21 chance on every spell,
arrow, damage event or attack that exits earlier in the hit routine. Faster or
more numerous eligible attacks provide more proc opportunities. The same
Dragoon class innate does not double the roll.
[Trigger](../../../src/combat/fight.c#L8355),
[damage](../../../src/combat/fight.c#L7292),
[follow-up to-hit](../../../src/combat/fight.c#L11538).

### Leap — `INNATE_LEAP`

The table lists Thri-Kreen at 21, but `leapSucceed()` admits **Thri-Kreen and
Harpy by race**, with **no `has_innate` or level-21 gate**. Both can avoid an
eligible incoming attack at any level if standing in normal condition and not
under Gaze. The chance is:

```text
clamp(1, AGI/7 - load_modifier/100 + (defenderL-attackerL)/2, 20) percent
```

It is an additional defense in the attack resolution path; it is not the
active Springleap skill, movement to another room or another attack. Gear
burden, AGI and level comparison affect it. A level-21 “unlock” announcement
does not mark a new avoidance benefit in current code.
[Race gate and roll](../../../src/combat/fight.c#L9150),
[hit resolution](../../../src/combat/fight.c).

### Vampiric Touch — `INNATE_VAMPIRIC_TOUCH`

PC Vampire has this at 1, giving the same touch-vamp bit as the temporary spell.
For eligible PC melee/touch damage it heals a fraction of actual damage based
on class. Committed fractions are **70% Antipaladin/Dreadlord/Avenger**, **25%
Monk/default**, **18% Berserker**, **17% Rogue**, **15%
Mercenary/Warrior/Ranger**, **10% Paladin**. The class checks have precedence
for multiclass characters; original Illithid's special default branch is only
relevant if it acquires the bit from another source. Arrow damage of at least
4 can heal **5%**, unless Battle Ecstasy is active.

Vamp healing can exceed normal maximum HP up to the POW-based `VAMPPERCENT`
cap, ordinarily `clamp(1.10,POW/90.0,2.50)`, plus the configured class/general
cap adjustments. It is blocked by a construct victim, negative energy barrier,
no-vamp flags and relevant form restrictions. The usual touch branch stops in
Vampire Form; that form has a separate trance-vamp branch, so the total form
behavior is not “no healing.” Existing earlier vamp sources can consume the
eligible opportunity. Normal Vampiric Touch spell hitroll is not part of the
innate bit: the innate does not automatically add that spell's hitroll affect.
[Bit](../../../src/magic/affects.c#L794),
[fractions and precedence](../../../src/combat/fight.c#L5848),
[gates and arrow/touch branches](../../../src/combat/fight.c#L5920),
[form branch](../../../src/combat/fight.c#L6047),
[caps](../../../src/core/utils.h#L1419),
[properties](../../../lib/duris.properties#L112).

The shared `vamp()` endpoint also refuses building-state healing, applies
plague/carrier and certain mantle/flamestrike healing blocks, can receive an
eligible healing-aura improvement, truncates fractional HP and stops at the
selected cap. Thus the class fraction is a potential heal before these shared
conditions, not guaranteed HP returned on every eligible hit.
[Healing endpoint](../../../src/combat/fight.c#L679).

### Hatred — `INNATE_HATRED`

Mountain Dwarf at 21 gains **-1 combat pulse and -1 spell pulse** while a
visible Orc, Duergar or Drow occupies the same room. No fight, hostile side or
enemy-player requirement exists: a visible NPC or friendly/grouped member of
one of those exact races can activate it. More hated occupants do not stack
more bonuses. An invisible/hidden target that the dwarf cannot see does not
activate the watcher.

The watcher runs every `innate.timer.hatred` **raw pulses**: committed 4 =
**1 second**. It owns exactly two unlimited, nondispellable, unsaved affects
while a matching target is visible, normalizes malformed duplicates and removes
them when the condition ends. Scheduled checks introduce up to one interval of
entry/exit lag. Losing eligibility/race clears it on the watcher path; it does
not permanently save the speed bonus. -1 spell pulse changes `SPELL_PULSE` by
**-0.03**; combat pulse goes through its nonlinear formula, not a flat one-second
speedup. Pulse floors and other modifiers can limit the benefit.
[Hated IDs](../../../src/core/constant.c#L2128),
[watcher and cleanup](../../../src/classes/innates.c#L5770),
[pulse formulas](../../../src/core/utils.h#L1406),
[regression](../../../tests/async/test_innate_hatred.py).

### Spirit of the Rrakkma — `INNATE_RRAKKMA`

Githzerai at 21 gains bonuses **for each other PC in its group and room that
also owns Rrakkma**. Each adds **-10 final calculated AC**, while shrug gains
**+5 rating** for up to **5 other holders**. The AC loop has **no corresponding
five-holder cap**; it remains subject to the final AC clamp (-750..100).
The ordinary holder can therefore have up to +25 shrug rating from this
setting, but larger same-race groups can continue adding AC until the final cap.
The loops explicitly test PC status, shared room and innate ownership; they do
not add a separate alive/conscious/standing check for the counted holder. This
is not a benefit from merely grouping with any race.

At 56, one Githzerai alone has base shrug 20/101; with five other eligible
holders it has **45/101**, before penetration/desecration. An ally receives no
Rrakkma bonus unless it owns the innate too. AC is added after ordinary armor
scaling and AGI/burden calculations, so -10 calculated AC is more direct than
-10 on an equipment item. [Shrug](../../../src/classes/innates.c#L4916),
[AC and final clamp](../../../src/combat/fight.c#L6748),
[settings](../../../lib/duris.properties#L1965).

### Warcaller's Fury — `INNATE_WARCALLERS_FURY`

Orog at 21 receives an outgoing **raw-damage modifier** based on the
victim's group and its own holder group:

```text
base = clamp(0.02, otherPCsInVictimGroupHere/100.0 + L/1120.0, 0.15)
extra = min(otherGroupedPCFuryHoldersHere,10) / 30.0
predicate bonus = base + extra
```

The committed cap is **10** other holders, larger than the fallback of 3 in
code. At 56, an ungrouped victim gives 5% base; ten other holders add 33.33%,
for 38.33% in that predicate. The target-group base caps at 15%, so the maximum
combined predicate bonus is about **48.33%**. It boosts the holder's damage,
not everyone's damage in the group, and does not supply another attack. Group
size is counted on the **victim**, excluding that victim, in the first term.
Both normal spell damage and melee damage eventually call `raw_damage`, so this
can also increase spells that reach it; it is not confined to weapon swings.
Raw-damage gates, multiplier caps and earlier exits still determine the result.
[Helper](../../../src/combat/dam_mods.c#L228),
[consumer](../../../src/combat/dam_mods.c#L1003),
[group count](../../../src/guild/group.c#L1137),
[spell-to-raw delivery](../../../src/combat/fight.c#L4873),
[setting](../../../lib/duris.properties#L1967).

## 7. Physical attacks, control and doors

### Bodyslam — `INNATE_BODYSLAM`

Barbarian, Firbolg, Ogre, Troll, Revenant and Wight receive this at 1. It is an
**opening control attack**, refused when the actor already has an opponent and
by the direct command while riding. It needs **30 vitality**, a legal target
after guard redirection and ordinary fight checks. Its base 60 chance is
multiplied by `clamp(80,100+actorL-targetL,125)/100` and
`clamp(60,100+(actorAGI-targetAGI)/2,155)/100`, then reduced to 80% against
Awareness and passed through shared takedown checks without that helper's
separate AGI check. It is not simply a 60% race-only roll.

The target must stand and be no larger than the actor, and no more than two
sizes smaller. Vitality is deducted after the shared takedown call, including
its rejection branches. A successful slam makes the target prone, engages,
gives **12s target and actor lag**, deals `STR-table todam+5` through the
physical damage path, and has a **1/2** follow-up stun lasting **4..10s** before
fear-save shortening/immunity rules. Failure can put the actor down, with
**8s lag** and a **1/2 4s self-stun** on the slip branch. Other failure/size
branches use their own lag. Surviving attempts normally leave the target with
**2 game hours of Awareness**, making repeated control harder.

Large native size is useful for target eligibility, high AGI for chance and STR
for damage; Enlarge can open or close size windows. Groundfighting does not
cancel the slam but makes being down less costly for its holder.
[Formula and flow](../../../src/cmd/actoff.c#L11526),
[shared takedown](../../../src/cmd/actoff.c#L11586),
[detailed size rules](race-size.md).

### Charge — `INNATE_CHARGE`

Minotaur at 11 receives the racial goring charge, distinct from a lance charge.
Without the innate, `charge` routes to lance charging; certain mounted knight
classes/specs also route there despite the racial grant. Racial Charge is
refused during an existing fight, in water/unsupported planar terrain,
single-file/tunnel rooms, or while its hit-generated cooldown remains. A low
underworld ceiling causes a **4s knockout**. It can acquire a victim in a named
direction as well as its own room, with the movement path's restrictions.

Base chance is **65** from committed settings, then actor Luck can multiply
1.10 and target Luck 0.90; add bounded **-20..20** level and STR-versus-AGI
terms. A prone target multiplies ordinary chance by .05, another nonstanding
posture by .15, Awareness by .80; Guardian Spirits subtract target level. The
ordinary chance caps at 95%, but immobile/asleep targets have a separate hit
override. Targets must be within **one size** of the charger; otherwise the
charger falls and an idle target can retaliate.

A hit deals `2*(number(1,L)+L)` base melee/touch damage (**114..224 at 56**),
gives the target **6s lag**, and starts **12s** of `SKILL_CHARGE` rest. If the
target is no larger, **1/3** of hits attempt the sitting/prone knockdown branch.
The actor ordinarily spends **30 vitality** and receives **8s lag**; these are
not the generic 720s innate timer. A directional miss can overshoot, including
a possible ocean splash. The old comment claiming roughly 42 damage at 56 is
not the current base damage formula.
[Admission and values](../../../src/cmd/actoff.c#L1400),
[chance and outcome](../../../src/cmd/actoff.c#L1710),
[configured base](../../../lib/duris.properties#L2050).

### Stampede — `INNATE_STAMPEDE`

Centaur at 21 can attempt room-wide knockdown, **PC-only**, with footing, front
rank and sufficient room width. It has **60s rest** by default, independent of
the generic timer default. It reveals the actor and considers visible targets
allowed by `should_area_hit`; it does not blindly hit every ally/neutral in the
room. Back-rank targets dodge. Ghosts, air elementals, efreet, elites and
phantasmal forms are explicitly immune.

For other front-rank targets there is a **1/10 automatic-hit branch**; otherwise
`number(1,100)` must not exceed
`actorL-targetL-I(targetAGI)+dice(10,aware?5:10)`. Hits make the target prone
and attempt a **2s fear-checking stun**, with no direct damage. The successful
hit limit is reevaluated as a random 2..3 while iterating; this is not one fixed
2-or-3 draw at activation. Existing opponents remain engaged with their prior
target; an idle candidate can start fighting the Centaur even if it dodges.
Actor lag is **4s for two or more hits**, otherwise zero. Cooldown can therefore
be spent without a successful hit or actor lag.
[Handler and formula](../../../src/cmd/actnew.c#L410),
[area eligibility](../../../src/core/utility.c#L5390).

### Bite — `INNATE_BITE`

Thri-Kreen at 11 and PC Vampire at 1 use the same innate ID, with variants
selected from **`GET_RACE2`**. The handler checks fight admission, readiness,
guard redirection and admission again, then spends a configured rest of
**12 seconds** (the `innate.timer.bite` helper's fallback, passed as a supplied
duration). It does
not require or consume a memorized poison spell. Default uses remain one.
[Dispatch and rest](../../../src/classes/innates.c#L2200),
[readiness/guard ordering](../../../src/classes/innates.c#L2278).

- **Thri-Kreen/insect-style:** hits unless `L+I(actorAGI)` is below a random
  `1..(targetL+2*I(targetAGI))`. Miss gives **4s lag**. A hit deals random
  **L..3L raw damage** and attempts poison `1+L/12` times, stopping at the first
  failed magical spell save. Modifiers descend from attempts-1 to 0. At 56:
  **56..168**, up to **5** saves. Physical delivery bypasses magical shrug,
  but uses `NewSaves`; trusted/undead targets resist poison's application.
  Surviving hit gives 4s lag. Lifeleak later removes **10 HP every 20s**, floored
  at 1, or every **60s under Slow Poison**. It has a **1/21** termination roll
  per poison invocation, a common ordinary affect duration (committed 4), and
  cure/aid interactions. It is not a direct kill-through-the-floor effect or
  an automatic separate regeneration penalty.
- **Vampire:** base **2dL melee damage**, **12s actor lag**, and, if both
  survive and the target lacks `TAG_VAMPIRE_BITE`, **30/101** chance of a
  **4s fear-checking stun** if not already stunned. It applies ordinary
  **`-max(1,L/10) CON`** for **2..4 game hours** regardless of that stun roll.
  At 56: **2..112** base damage and **-5 unscaled CON**, transformed by the
  target's CON factor/caps. Existing bite prevents both secondary effects but
  not the damage attempt. This bite itself does not call the damage routine
  with `PHSDAM_TOUCH`, so owning Vampiric Touch is not proof it heals from this
  particular attack.

Snake shapes use a delayed venom strike; parasite shapes use their separate
damage/AGI-save/disease logic. These variants matter when a PC obtains a shape,
but snake/parasite are not additional native PC grants.
[Vampire variant](../../../src/classes/innates.c#L1830),
[venom and poison](../../../src/classes/innates.c#L1920),
[variant switch](../../../src/classes/innates.c#L2160).
The legacy Vampire heal/charm block below the immediate return is unreachable.
[Lifeleak](../../../src/world/handler.c#L909),
[common poison duration](../../../src/world/handler.c#L858).

### Ogre Roar — `INNATE_OGREROAR`

Ogre at 11 has a debuff with default rest and **no explicit lag**. Rest is
spent before most posture/target/size/hearing checks. It cannot affect a larger
target, either Illithid race, an unconscious/sleeping/inadequately alert target,
an already-roared target, or one in a silent room. It requires normal fight
admission. No ordinary magical shrug or saving throw is called.

```text
t = clamp(1, number(1,101)
    + (targetL-actorL)/10
    + (targetPOW-actorPOW)/15 + (targetWIS-actorWIS)/15
    - (target has Fear or Meditate ? 5 : 0), 101)
```

- `t=1`: target AC worsens by `L+10`, hitroll falls by
  `targetHitroll*L/60`, duration `20-t/7` = **20 game hours**.
- `2..67`: target AC worsens by `L`, hitroll falls by
  `targetHitroll*L/90`, for `15-t/7` (**6..15 game hours**).
- `68..100`: no debuff; an NPC that sees the actor can remember/retaliate.
- `101`: **target** AC worsens by `1+targetL/2`, but **actor** hitroll falls by
  `actorHitroll*targetL/100`, for `10+t/7` = **24 game hours**. This mixed-subject
  worst result is what the source does despite its comment describing both
  penalties on the actor.

With zero modifiers, ordinary success is 66/101, best 1/101, no-effect 33/101,
worst 1/101. Clamping means nonzero stat modifiers can greatly change the best
and worst probabilities. The handler lacks the advertised “plain Ogre only”
native-race rejection after the ownership check; do not infer that gate from
its description. [Handler and outcomes](../../../src/classes/new_skills.c#L3354).

### Web Spray — `INNATE_WEB_SPRAY`

Drider at 31 fires a **physical vitality drain**, not the older Webwrap
immobilization. A legal target spends **300s rest and 4s lag**, then Freedom of
Movement and eligible Evade can defeat it; the attempt reveals and engages.
No spell shrug or ordinary save is used. With `d=actorAGI-targetAGI`:

```text
chance = clamp(5, .70*(1.5L)
                 + .30*clamp(0,100+d*(d<=0?2.0:.5),125), 90)
```

`number(1,100) <= chance` hits. At equal AGI: 62% at 31, 88% at 56 after the
integer roll threshold. A hit replaces the old Web Spray affect and lasts
**30 real seconds**, draining `L/8` vitality every **4 seconds**, floored at
zero; at 56 this is **7 per drain**. It does not directly drain mana/HP, impose
command lag on every tick or forbid movement. Each completed room move has a
**10%** chance to tear free. The affect is short/nondispellable; removal
disarms the drain, and restoring it recreates the periodic owner.
[Handler and drain](../../../src/classes/innates.c#L5305),
[move escape](../../../src/classes/innates.c#L5488),
[restore scheduling](../../../src/magic/affects.c#L2088),
[cleanup](../../../src/magic/affects.c#L2325).

### Doorbash and Doorkick

`INNATE_DOORBASH` belongs to Barbarian, Firbolg, Ogre, Troll, Minotaur, Revenant
and Wight at 1; `INNATE_DOORKICK` to Centaur at 1. Neither has an innate reuse
timer or explicit vitality cost. Both require a connected character, an
eligible closed visible door, and no riding. Specials can intercept the
direction. Pickproof, missing-destination and `_nobash_` doors do not give;
secret/blocked doors are not ordinary mortal targets. Success clears local
locked/closed flags and the matching reverse side, rather than destroying the
exit record permanently.

| Outcome | Doorbash | Doorkick |
|---|---|---|
| Success chance | `40+L` against 1..100; 96% at 56 | `45+L`; certain at 55+ for eligible doors |
| Self damage if success | `2d(number(1,10))`, range 2..20 | `2d5`, range 2..10 |
| Self damage if ordinary failure | `3d(number(2,8))`, range 3..24 | `2d(number(1,10))`, range 2..20 |
| Self damage if unbreakable | `3d(number(2,10))`, range 3..30 | `2d(number(2,10))`, range 2..20 |
| Actor lag if alive | 8s | 8s |
| Position after success | Through the door | Back in the starting room |

Doorkick **temporarily moves the actor through and back** to update the reverse
exit/messages. Room-entry effects can therefore occur even though its intended
final position is unchanged; an interrupted/deadly entry need not complete the
return. These abilities can cost HP and expose a route to everyone, so they
are not simply free substitutes for picking a lock.
[Doorbash](../../../src/classes/innates.c#L3869),
[Doorkick](../../../src/classes/innates.c#L4050).

## 8. Spell-like powers, forms and travel

### Darkness — `INNATE_DARKNESS`

Shade at 1 casts **room darkness**, default rest and **4s lag even when too
tired**. The room effect lasts **50L pulses = 12.5L seconds** (700s at 56).
An already magically dark room does nothing; a magically lit room loses its
light instead of also gaining a full new darkness effect. Otherwise it sets
`ROOM_MAGIC_DARK` with an expiry event and recalculates light. This changes
visibility for everyone in the room and can preserve shadows or mitigate the
HP-regeneration sunlight gate. It does not grant Ultravision, a personal globe,
or the mana-regeneration gate's missing magic-dark exemption.
[Wrapper](../../../src/classes/innates.c#L2394),
[room effect](../../../src/magic/magic.c#L22027).

### Globe of Darkness — `INNATE_GLOBE_OF_DARKNESS`

Drow at 26 self-casts the globe for **L/4+1 game hours**, default rest and **4s
lag**. At 56: 15 hours, nominally 1125s before update phase. It cannot coexist
with the caster's mage flame or another globe; these rejections occur after
the use is spent. The carried globe changes character/room light, supplies
personal exemptions from Dayblind, sunlight burn and the HP/mana sunlight
recovery blockers, and can affect other occupants' visibility through shared
light calculations. This is not the separate **Globe of Shadows** used in
illusion/pet permanence checks, nor a damage-blocking minor/major globe.
[Wrapper](../../../src/classes/innates.c#L3027),
[spell and light](../../../src/magic/magic.c#L17676),
[dayblind predicate](../../../src/core/utils.h#L1219),
[sun gates](../../../src/world/limits.c#L161).

### Faerie Fire — `INNATE_FAERIE_FIRE`

Drow at 1 can target an ordinary visible room victim/current opponent,
**4s lag and no innate rest**. It worsens AC by **20** for **5 game hours** and
does not stack on an existing Faerie Fire. The handler does not call magical
shrug or a saving throw. It clears invisibility/concealment bits and marks the
outlined target through the concealment-state branch; a target already visible
can lose a disguise on a **1/2** roll. It does not indiscriminately remove
every hide, non-detection or every stored invisibility affect.

The concealment-affect removal loop is guarded by **the caster having
`SPELL_CONCEALMENT`**, although it iterates the victim's affects. This unusual
subject matters when predicting lasting reveal versus a later recalculation.
An NPC that sees the caster can remember and attack. AC +20 on stored armor is
not always +20 final calculated AC because PC negative armor is scaled later.
[Handler](../../../src/classes/innates.c#L2644),
[spell and subject checks](../../../src/magic/magic.c#L18808),
[AC calculation](../../../src/combat/fight.c#L6753).

### Blast — `INNATE_BLAST`

Original Illithid at 1 gets an attempted paralysis, default rest, **no explicit
actor lag**. Planetbound Illithid has no racial Blast grant. Target parsing
precedes the timer; shopkeepers are ignored after the timer is spent.
The spell has **1/2** chance to reveal an unseen caster, then Freedom of
Movement can stop it. A **1/3** gate plus a failed POW stat save is needed;
NPC paralysis immunity and existing minor/major paralysis prevent application.
At actor level >25, **1/2** of applications use Major rather than Minor.
Duration is **`(L>>5)+1` game hours** (2 at 56).

The defender's POW save modifier is **`max(-3,(actorL-targetL)/3)`**: a higher
actor level can make the defender's save *easier*, the sign issue also recorded
in [stat issues](race-stats-issues.md). No general magical shrug is called by
this spell. Successful paralysis stops the victim's fight and invokes the
merciful-attacker stop rule, rather than guaranteeing every hostile attacker
will stop. It supplies no direct damage, death effect or mana drain.
[Wrapper](../../../src/classes/innates.c#L2622),
[application](../../../src/classes/psionics.c#L4005),
[paralysis state consumers](../../../src/core/utils.h).

Unlike Bite/Web Spray, the Blast wrapper does not run `CanDoFightMove`, guard
redirection or `should_not_kill` before invoking this status spell. Its inner
checks are the ones listed above, so standard attack-command admission should
not be assumed from the hostile nature of the power.

### Throw Lightning — `INNATE_THROW_LIGHTNING`

Kuo Toa at 30 spends default rest, must already be fighting, announces charge-up
and takes **4s lag**. Trying out of combat still spends the use. After **8s**
the event selects the actor's **current opponent**, rather than retaining the
original one. No opponent means the sparks disperse. It deals **`(3L)d5`
lightning spell damage**, range **3L..15L** (168..840 at 56), before spell/raw
modifiers, warding, shrug and other applicable defenses. It supplies no explicit
magical saving throw of its own. The current call passes flags **0**, so the
old spell-damage comment listing lightning among no-shrug exceptions is not an
actual `SPLDAM_NOSHRUG` flag here. No spell-circle globe/spirit-ward flags are
requested. There is no race-assigned Storm Giant lightning in current code.
[Charge and event](../../../src/classes/innates.c#L1715),
[spell-damage flags](../../../src/combat/fight.c#L4395).

### Fireshield — `INNATE_FIRESHIELD`

Death Knight at 31 self-casts Fireshield with **4s lag and no innate rest**.
Duration is **6 game hours**. Existing fire/cold/lightning shield prevents a new
elemental shield rather than stacking another; Infernal Fury takes precedence
in the retaliation code. The fire shield:

- Contributes the normal **-25% fire spell damage** branch instead of fire
  protection's -15%, or the weaker -10% branch on a fire-vulnerable holder.
- Adds **+50%** against cold damage in the relevant cold predicate with the
  committed opposite-shield setting; other cold modifiers can add inside that
  predicate. It is not all-element protection.
- Returns a fire spell hit through elemental-shield retaliation, configured
  `damage.shield.fireshield=0.65`, after the shield path's scaling/flags and
  the attacker's applicable spell defenses. This is **not** an unconditional
  extra 65% of all final damage taken, nor reflection of every projectile/spell.
- Interacts with fire-aura absorption only if the separate aura is present;
  PC Death Knight does not receive Fire Aura merely by having Fireshield.

[Wrapper](../../../src/classes/innates.c#L3160),
[shield exclusivity](../../../src/magic/magic.c#L17728),
[elemental modifiers](../../../src/combat/dam_mods.c#L377),
[retaliation](../../../src/combat/fight.c#L4970),
[fire aura gate](../../../src/combat/fight.c#L4452).

### Firestorm — `INNATE_FIRESTORM`

Death Knight at 26 has an area fire attack with **16s actor lag and no innate
rest**, calling Firestorm directly. Its area selection observes ordinary
eligible-target, position, chance-step and safe/group rules. Each selected
target receives **Ld10** base damage, halved by its magical save. Committed area
factor is **1.0**, and the PC-to-PC factor is **1.15** (the code fallback is
0.5). At 56 this is **56..560** before the save and defenses, or **64..644**
against a PC before save/integer rounding; the saved range is calculated in
the source's save-then-PC-factor order. It still uses normal spell defenses
including shrug, while no globe/spirit-ward flags are requested.

It also adds a short room Firestorm lasting **6s** normally (**8s** for Dragon
Priest) and dries wet occupants. The room becomes “hot”: **Ice Storm melts into
water instead of its cold hit**, and Avalanche's room-fire branch splashes a
target instead of its normal snow effect. Wet-state changes can then affect
their shared elemental damage rules. That room affect is not evidence of a
separately scheduled repeated Ld10 attack. Changing a native race does not by
itself grant the Dragon Priest specialization.
[Wrapper](../../../src/classes/innates.c#L3182),
[damage and room state](../../../src/magic/magic.c#L5501),
[settings](../../../lib/duris.properties#L948),
[area-fire consumer](../../../src/core/utility.c#L5927),
[Ice Storm](../../../src/magic/magic.c#L18739),
[epic interaction](../../../src/classes/epic_skills.c#L779).

### Stone Skin — `INNATE_STONE`

Wight at 25 self-casts Stone Skin, **300s fixed rest and 12s lag**, using its
level and **class-dependent charge multiplier**. Starting charges are
`L/4+number(1,4)`, then 1.5x with Living Stone/Mace of Earth, otherwise 1.2x
for Conjurer, 1.0x for Sorcerer, .8x for others (integer truncation). At 56 an
ordinary noncaster Wight receives **12..14 charges**, not the Conjurer's 18..21.
Duration is **4 game hours**. Existing incompatible skin spells can reject the
cast after spending the use; Earth Conjurer has the separate three-layer rule.

Eligible incoming melee hits consume skin charges, deduct the configured
**46** damage, then, if over 10 remains, apply **0.55** to the remainder.
Armor, earlier/later reductions and minimum damage still affect the result.
`PHSDAM_NOREDUCE` and qualifying Fist of Dragon bypasses do not consume these
skin charges. It is finite physical mitigation, not a fixed number of entirely
negated attacks, spell shrug, fire/cold protection or native size growth.
[Wrapper](../../../src/classes/innates.c#L3340),
[charges and stacking](../../../src/magic/magic.c#L11240),
[melee consumption](../../../src/combat/fight.c#L5590),
[settings](../../../lib/duris.properties#L196).

### Battle Rage — `INNATE_BATTLE_RAGE`

Duergar at 31 self-casts **Haste at level 60**, default rest and **8s lag**.
If slowed by `SPELL_SLOW`, it only removes that Slow; already hasted does
nothing, and either attempt still consumes rest/lag. Duration depends on class:
**30 game hours** for Air Conjurer, **15** for Ranger/Reaver/Conjurer/Sorcerer,
**10** otherwise. Racial ownership does not make every class get the longer
duration.

Haste supplies one additional base attack where the haste/slow attack branch
allows it, **80% ordinary casting time**, **+2 DEX stat-save score**, **+2 AGI
save score for non-Monks**, **+20 archery speed**, and bard beats **10 pulses
sooner**. These effects use their respective consumers and limits; an innate
wrapper's explicitly fixed lag does not become an ordinary spell cast merely
because Haste is active. It does not directly add a combat-pulse or spell-pulse
affect and does not stack twice with externally supplied Haste.
[Wrapper](../../../src/classes/innates.c#L3247),
[Haste and duration](../../../src/magic/magic.c#L12529),
[casting](../../../src/net/sparser.c#L990),
[songs](../../../src/classes/bard.c#L60),
[archery](../../../src/combat/range.c#L418).

### Phantasmal Form — `INNATE_PHANTASMAL_FORM`

Phantom at 20 gains invisibility, passdoor and the phantasmal-form bit for
**980 pulses = 245 seconds**, with default rest and **4s activation lag**.
Using the innate while already in form ends it before checking rest. Ordinary
invisibility detection still applies; passdoor does not override every sealed,
blocked, private or content-script restriction.

The bit joins `IS_IMMATERIAL` and consequently `LEGLESS`, changing physical
control/targeting admission across their shared consumers. It explicitly
blocks Combination, Hamstring and Stampede, qualifies the PC for Ethereal
Recharge/Greater Ethereal Recharge healing (and their blindness cure), and
bypasses the phantasmal checks in razor-hook/tower traps and several Tower of
Summonings doors/guard procs. Such content effects require those specials to
be assigned in the actual world; no world-assignment census was performed.

Its tradeoff is **+50% elemental spell damage** in that modifier branch unless
Awe armor is present. It does not reduce all physical damage to zero, grant
flight before Phantom's separate level-21 grant, or negate every trap.
Phantom is already one of the native immaterial races even without this form;
the form's additional bits, explicit checks and elemental penalty still matter.
[Handler](../../../src/classes/innates.c#L3288),
[immaterial/legless](../../../src/core/utils.h#L139),
[elemental penalty](../../../src/combat/dam_mods.c#L724),
[Combination](../../../src/cmd/actoff.c#L3353),
[Hamstring](../../../src/cmd/actnew.c#L4066),
[recharge](../../../src/classes/ethermancer.c#L1776),
[traps](../../../src/specs/specs.hoa.c#L55),
[tower specials](../../../src/specs/specs.shabo.c#L343).

### Astral Shift and Prime Shift

`INNATE_SHIFT_ASTRAL` is level 1 for original/Planetbound Illithid, Githyanki
and Phantom, but **45 for Githzerai**. `INNATE_SHIFT_PRIME` is level 1 for all
five. They have **independent default 720s timers**. Both reject an active
fight (adding **4s lag**) and recent PvP delay (no wrapper lag in that branch).
Successful dispatch adds 4s lag. These are self-travel abilities, not group
portals and not the class `INNATE_PLANE_SHIFT` command.

**Astral:** calls the shared Plane Shift cast path with destination `astral`.
It retains raidability, hometown/no-gate, destination no-magic, same-plane and
destination selection checks. A Druid class can still trigger that path's
level-41 restriction, even if the racial grant is earlier; rest has already
been spent when these inner checks fail. It does not bypass every travel ward.
[Astral wrapper](../../../src/classes/innates.c#L2421),
[shared plane casting](../../../src/magic/spells.c#L738).

**Prime:** only works in the **zone containing room 19701**, not every room
whose sector/name is “astral.” It chooses a race-specific destination slot:

- Githyanki/original Illithid/Planetbound Illithid: **15** slots; four select
  an eligible random room in Clavikord, Bugentolen, Storm Port or Quietus Quay.
- Githzerai: **14** fixed slots.
- Phantom: **9** fixed slots.

Unavailable slots are excluded; usable slots have equal odds, then random-zone
rooms have equal odds within their chosen slot. The larger number of rooms in
a zone does not give that slot more weight. Random-zone candidates reject
private/no-magic/no-teleport/no-gate rooms, hometowns, ocean/no-ground sectors
and failed entry admission. Fixed slots have a different selection filter and
still pass through `char_to_room`. Finding no usable path spends the use and
does not add the final success lag. The native-race destination branch can
disagree with shape-based ownership. These are random navigation networks,
not player-selected recall points.
[Prime destinations and filters](../../../src/classes/innates.c#L2474),
[Prime execution](../../../src/classes/innates.c#L2549).

### Shadow Door — `INNATE_SHADOW_DOOR`

Revenant at 25 casts Dimension Door toward a named visible world character,
default rest. Fighting or recent PvP rejects before the timer. Missing/invalid
target also rejects first; the underlying travel restrictions can fail after
the use is spent. With the committed distance factor **1.25**, range is
`int(1.25L)` rooms (**70 at 56**), +15 for Shadow Sorcerer. Ordinary PC lag is
**9s**, Shadow Sorcerer **1s**, Air Conjurer **3s**; the spell adds lag before
its inner rejection checks.

Non-detection/no-locate, raidability, staff targets, racewar, hometown/no-teleport,
ocean, castle-sector and ridden-NPC checks can prevent travel, and graph range
must succeed in at least one direction. It transports the actor, not the
target/group. Revenant regeneration does not remove these restrictions.
[Wrapper](../../../src/classes/innates.c#L3201),
[range, lag and gates](../../../src/magic/magic.c#L7256),
[setting](../../../lib/duris.properties#L964).

## 9. Summons, images, equipment and economy

### Reflection — `INNATE_REFLECTION`

Gnome and Kobold at 31 self-cast the Illusionist Reflection spell, **300s
configured rest and 4s lag**. It creates
`clamp(1,(L-26)/5,4)` images: **1 at 31, 2 at 36, 3 at 41, 4 at 46+**.
Each image has **4L+number(0,50) HP** (224..274 at 56), copied race/sex/size/
appearance and detect invisibility, but template-derived combat details rather
than a complete copy of the player's build.

The images are controlled followers; the spell redirects characters currently
fighting the caster onto one image, so the immediate combat disengagement can
be more important than their own damage. This is **not** a percentage chance
to bounce incoming spells, four automatically negated hits, or an AC buff.
Recasting extracts existing image followers before creating replacements.
Titan-illusion ownership rejects **before** the innate cooldown/lag; the
wrapper always targets its owner regardless of the argument. Images normally
receive **3 game hours** of pet control, extended indefinitely by the shared
Globe of Shadows/Unholy Alliance setup rule. Other summoning/pet limits,
attacker retargeting and subsequent area damage can reduce their practical
survival. A PC's group does not automatically get its own images.
[Innate wrapper](../../../src/classes/innates.c#L3367),
[image count and HP](../../../src/classes/sillusionist.c#L905),
[creation and redirection](../../../src/classes/sillusionist.c#L944),
[pet control](../../../src/classes/necromancy.c#L251),
[focused regression](../../../tests/async/test_innate_reflection.py).

### Project Image — `INNATE_PROJECT_IMAGE`

Shadow Beast at 1 loads **mobile 250**, strips existing affects, copies its
name/title/race/sex/alignment/size, clears plushit properties and places the
image in its room. A valid direction argument makes that mobile issue one
movement command. **4s actor lag, no rest**, no explicit image-count limit in
this handler. It does **not** call `setup_pet`, link a follower, copy all stats,
redirect current attackers or implement the Reflection spell's expiry/count
rules. It can provide a visual decoy or a mobile sent through an exit; the
template's flags/specials and room-entry effects determine further behavior.
It is not a guaranteed player-controlled scouting camera or a second body the
player can possess. Prototype absence aborts the load.
[Handler](../../../src/classes/innates.c#L3097),
[checked-in legacy template](../../../areas/mob/heavens.mob#L1351).

### Summon Horde — `INNATE_SUMMON_HORDE`

Orc at 11 calls up to `clamp(1,L/10,20)` Orc followers, counting existing
**linked Orc NPCs**; at 56 the cap is **5**. Each new mobile 4007 is forced to
**level 1 and 1 HP**, with no aggression, pet/follower setup and no cash/XP
reward. These are fragile bodies for orders, blocking and follower interactions,
not five level-56 damage pets. The shared pet system supplies owner links and
control rules; no innate-specific despawn timer is installed for this horde.

Default rest, **no explicit actor lag**; arrival delay is
`number(70-L,70)` **pulses** (3.5..17.5s at 56). An ordinary PC must still
have native `RACE_ORC`, even if shape/class ownership would admit the command.
Off-prime/ocean rejects after spending a use; locker/single-file and existing
linked-Orc count are checked at arrival. Because the event belongs to the
actor, moving can change the arrival room and its eligibility. The existing
count checks linked Orc NPCs rather than only objects created by this ability.
[Handler and payload](../../../src/classes/new_skills.c#L3205),
[shared pets](../../../src/classes/necromancy.c#L251).

### Summon Warg — `INNATE_SUMMON_WARG`

Orc at 16 has this active assignment; the Goblin comment block is misleading.
One existing mount follower blocks a second call, regardless of whether it is
literally a warg. The initial call needs outdoors or underworld and no locker;
the delayed arrival normally needs prime plane, no ocean/single-file/locker,
and no existing mount. **Default rest, no explicit actor lag.**

The shared mount arrival selects the prototype by **class/race precedence**:
paladin/antipaladin paths can win before Orc/Goblin mobile 39, and Dragoon has
other special behavior. For an ordinary Orc warg at level 56:

```text
delay = number(70-L, 100+number(1,200-2L)) pulses
factor = max(1,int(.75L+number(-5,5))) = 37..47
mount level = 10+factor = 47..57
mount HP/base HP = 50*factor = 1850..2350
```

The full delay envelope at 56 is **3.5..47s**, not 70 seconds. Base STR/AGI/CON
are bounded between 75 and `75+factor`; CHA is set to 100, class to none and
mount flag on. The generic code grants **Fly above actor level 50**, so a
high-level ordinary Orc can summon a flying warg. Extra knight/Dragoon mount
protections depend on the caller's class/spec and should not be credited to
every Orc. The mount can enable riding travel and mounted mechanics but still
needs rider eligibility/skills; a summoned mount is not automatic mastery of
mounted combat. A failed arrival can leave the cooldown spent.
[Call](../../../src/classes/new_skills.c#L3164),
[delay](../../../src/classes/new_skills.c#L3040),
[prototype selection and scaling](../../../src/classes/new_skills.c#L2790),
[mount admission](../../../src/classes/mount.c).

### Summon Totem — `INNATE_SUMMON_TOTEM`

Goblin at 26 loads **object 417** and submits a named personal replacement
totem. **4s delay, no reuse timer and no explicit lag.** It is an equipment
object placed in inventory; its bonuses require an eligible active equipment
slot through normal aggregation. Repeating the summon replaces the older
personal summoned item through the grant-completion path, preserving the
existing item if the new grant fails. It is not an unlimited permanent stack
of the same worn bonuses.

The handler adds these powers cumulatively at current summoning level:

| Level | Added property | Gameplay effect when equipped |
|---|---|---|
| 26 | Personal summoned totem/template | No extra tier below 31 in this handler; template properties still matter |
| 31 | Farsee | Directional information and improved-track roll benefit |
| 36 | Sense Life | Hidden-life presence messages and a chance to notice sneaking movement; not blanket `CAN_SEE` on hidden creatures |
| 41 | Soulshield | Eligible opposite alignment/racewar melee reduction (0.90), holy-damage reduction (0.90), negative-damage vulnerability and eligible holy retaliation |
| 51 | +10 `APPLY_HIT` | Raises maximum HP through ordinary equipment aggregation |
| 56 | -1 spell pulse | Changes spell-pulse multiplier by -0.03, subject to other pulse rules |

Existing objects do not automatically upgrade because the character levels;
the code assigns these fields when creating a replacement. The handler clears
`bitvector` but does **not** clear all other template flags/affects before
adding tiers. The legacy checked-in object describes a held totem, but live
SQL/prototype overrides were not inspected, so these added tiers are not a
claim that its entire runtime object has no other properties.

Soulshield's **spell reduction is in the holy predicate**, not a blanket 10%
off every spell. Its negative-damage predicate uses
`damage.soulnegshield.increase` (absent in committed properties, fallback
**1.5**, or +50% in that predicate). The melee reduction and holy touch
retaliation require opposite good/evil alignment or opposite racewar; neutral
or same-side opponents are not automatically affected. The bit also prevents
ordinary Negative Energy Barrier application, and spell-type-specific bonuses
requiring an actual `SPELL_SOULSHIELD` affect are not supplied by merely wearing
the totem. These tradeoffs matter when deciding whether to equip it.
[Creation and tiers](../../../src/classes/new_skills.c#L2700),
[replacement completion](../../../src/classes/new_skills.c#L185),
[equipment aggregation](../../../src/magic/affects.c#L1719),
[legacy object](../../../areas/obj/heavens.obj#L4389),
[Soulshield damage](../../../src/combat/dam_mods.c#L575),
[negative damage](../../../src/combat/dam_mods.c#L605),
[barrier conflict](../../../src/magic/magic.c#L17805),
[Soulshield retaliation](../../../src/combat/fight.c#L5082).

### Call of the Grave — `INNATE_CALL_GRAVE`

Lich at 1 can invoke the same command as the class skill, using **skill `L+50`**
for its summoned payload. It needs footing, and skeleton arrival fails in a
single-file room. It uses **`SKILL_CALL_GRAVE` rest of 60 base rounds = 240s**,
**8s actor lag**, and a delay of `4*(5+1d5)` pulses = **6..10s**; it does not
use the general innate timer. At arrival:

```text
count = clamp(1,(L+50)/10-number(0,5),6)
skeleton level = clamp(6,L-number(15,35),42)
HP/base HP = L*number(3,5)
hitroll = skeletonLevel/2; damroll = skeletonLevel+10
despawn = 60+3*(L+50) real seconds
```

At 56: **5..6 skeletons**, level **21..41**, **168..280 HP** each, living for
**378s** before explicit extraction. Each loads mobile 16, receives the shared
pet/follower link, zero cash/XP, and randomly selects Warrior (1/5), otherwise
Dreadlord (1/6 of the remainder), otherwise no class. Since despawn can exceed
the rest, the handler does not itself forbid successive waves from overlapping.
Control duration and despawn are separate; indefinite charm from another source
does not remove the scheduled grave-return event.

Naming a target does **not** turn ordinary Lich ownership into the Deathlord's
direct ground-strike damage branch; that additionally requires the Dreadlord
Deathlord specialization. Invalid targets can reject before scheduling/rest;
moving before the event changes where skeletons arrive.
[Skill/rest/payload](../../../src/cmd/actoff.c#L12682),
[summon and despawn](../../../src/cmd/actoff.c#L12846),
[pet control](../../../src/classes/necromancy.c#L251).

### Seadog — `INNATE_SEADOG`

Human and Orc at 1 add **+2 to ship maximum speed** when that character is
passed as the sailor/helm actor to `get_maxspeed(ch)`. The ship's actor-less
base speed does not permanently rise, and a passenger does not grant every
helmsman +2. It also multiplies **ordinary cargo sale proceeds by 1.10**,
subject to integer rounding, price/profit, diplomat, warship and nexus rules.
It does **not** boost contraband sales or ordinary shop selling/buying prices.

Both legacy ship trade and durable Divine trade consult the seller's innate.
In the Divine path the separately computed qualified-cargo extra payout is
outside that ordinary-sale multiplication; “all final trade revenue +10%” is
therefore too broad. Swashbuckler can obtain the same innate at 30, so the
racial edge is early access or access on another class, not a second stack on
a level-30 Human/Orc Swashbuckler.
[Speed and fraction](../../../src/ships/ship_utils.c#L880),
[legacy sale](../../../src/ships/ship_shop.c#L970),
[Divine settlement](../../../src/economy/divine_trade_runtime.c#L972),
[class overlap](../../../src/classes/innates.c#L894).

## 10. What the differences mean for each race

These are qualitative consequences of the traced mechanics, not race rankings.
Native stats, gear, class options and non-innate racial factors can outweigh a
listed advantage. A race with few innates is not thereby a weak race.

| PC race | Practical innate differences and tradeoffs |
|---|---|
| Human | Early ship speed/cargo profit, with no innate land-combat or special sight package. The separately configured Human stat bonus is not a Seadog effect. |
| Barbarian | Bodyslam/door access from 1; at 21 knockdown costs less damage, attacks and dodge; at 31 cold protection; at 41 ordinary fear immunity. Several benefits are late, and ordinary stun/lag still works. |
| Drow Elf | Early night sight, shrug and repeatable Faerie Fire; level-11 float/longsword bonus; level-26 globe mitigates sun/recovery restrictions. Sun vulnerability exists before that self-mitigation tool, and the globe can be unavailable or conflicted. |
| Grey Elf | Infra, meaningful shrug, longsword specialization and forest information; free field/forest/hill movement concealment arrives later than Wood Elf's. No innate sunlight penalty. |
| Mountain Dwarf | Generic spell mitigation from 1, specialized giant dodge score, early STR/axe, then visible-enemy speed and hammer choice. Its magic reduction does not stop elemental or status spells; Hatred needs specific visible races. |
| Duergar Dwarf | Generic spell mitigation and night sight plus active shadow invisibility, STR, combat proc, size growth and Haste. Powers ramp through 6/16/26/31; sunlight, restricted invisibility activation and cooldown waste constrain them. |
| Halfling | Reliable hidden-state access, early save rerolls/quaff benefit, later tracking/map information and final +10 Luck. No native dark-vision bit; Luck affects many conditional thresholds rather than one universal damage multiplier. |
| Gnome | Both vision bits, Farsee and later self-image disengagement. No assigned Magic Resistance despite the theme of magical aptitude; images and gear/class defenses provide a different protection model. |
| Ogre | Early opener/door access, later major hitroll/armor debuff and night sight. Magic Vulnerability and sunlight impair caster matchups and recovery; Roar has stat/size/hearing failures and a possible self-hitroll penalty. |
| Troll | Very large recovery, later melee mitigation and swamp travel/concealment. Fire both hurts more and suppresses native recovery; sun blocks recovery; no current Groundfighting protects its downed attacks/dodge. |
| Half-Elf | Infra, longsword and shrug from early levels; Quick Thinker arrives at 30 rather than Halfling's 1. Its same-tier magical shrug base is modest, while the save reroll addresses a different defense stage. |
| Illithid | Very high shrug base, early float, both astral routes and paralysis attempt, but sun vulnerability. Blast uses a separate random/stat-save path; low innate count on another race does not imply access to these travel/control powers. |
| Orc | Night sight and nominal Dayvision, horde bodies, later a scaling mount, and early naval economy. It has no assigned Magic Resistance or sun penalty; Dayvision itself has no active benefit. |
| Thri-Kreen | Night sight, poison bite, and race-based avoidance already below its listed Leap unlock. Cold can add both damage and Slow; avoidance needs posture and fails under Gaze. |
| Centaur | Body stability/equipment/rearkick plus doors, multi-target knockdown and later automatic two-handed slashing rating. It cannot normally ride another mount, and body protection is action/size-specific. No innate dark vision. |
| Githyanki | Early two-way astral network and shrug, then float; sun restricts surface recovery. Prime return destinations differ from Githzerai/Phantom, and recent PvP disables these travel wrappers. |
| Minotaur | Night sight, doors and goring charge with directional mobility/damage/control. No innate Magic Resistance or sunlight penalty; charge needs viable terrain, vitality and a tight target-size window. |
| Shade | Night sight, room darkness and later hidden travel through shadows. Fire weakness; shadow travel fails in lit/twilight destinations and does not transport the PC instantaneously. |
| Revenant | Opener/doors, high recovery and later ranged ally travel through Shadow Door. Fire vulnerability remains; no innate sunlight penalty, but no Troll Skin or Groundfighting either. |
| Goblin | Night sight, progressively stronger summoned equipment and repeatable in-fight hiding. Its final spell-speed improvement requires the totem to be generated at 56 and actively equipped. It does not own the Warg assignment in its comment block. |
| Lich | Strong shrug, Eyeless, lower-undead aggression protection, cold protection and recurring skeletons; from 21 slot-dependent absorb. Sun/recovery restrictions remain, and absorb is wasted on full slots or a non-slot resource model. |
| Vampire | Persistent eligible-hit healing, separate bite/CON/stun attack, shrug and late holy-damage reduction. Sun remains a constraint; current native PC grants have neither Gaze nor fire weakness. Bite is not the unreachable legacy heal/charm code. |
| Death Knight | Native fire protection plus free-to-reuse Firestorm/Fireshield after 26/31. Fixed command lag still limits throughput; sunlight remains, and the shield creates elemental tradeoffs rather than all-damage immunity. |
| Shadow Beast | Immediate STR, Enlarge, underworld sneak, night sight and repeatable visual decoys. Fire vulnerability; Project Image is not Reflection's linked pet/disengagement mechanic. |
| Storm Giant | No racial table innates. Its size/stats/racial factors and class abilities still matter; inactive source comments do not provide doors or lightning. |
| Wight | Early opener/doors/night sight, later finite-charge Stone Skin. Fire weakness; its ordinary class can produce fewer skin charges than a Conjurer with the same level. |
| Phantom | Early astral travel/night sight/shrug, form at 20 and sustained Fly at 21. Fire weakness combines with the form's separate elemental penalty; form permits recharge healing and selected physical/content exemptions. |
| Harpy | Continuous Fly, information range/track bonus and night sight from 1. It also receives the race-based leap defense despite no Leap table entry; no native fire/cold/sun weakness is assigned here. |
| Orog | Night sight and later damage scaling from its victim's group and its own Fury-holder group. Sun constrains recovery. Group scaling is personal output and can apply through the spell-to-raw path too. |
| Githzerai | Shrug/night sight and later float, with group-only AC/shrug scaling from 21. Prime return is available at 1, but outgoing Astral Shift waits until 45; no assigned sun penalty. |
| Drider | Body stability/equipment, shrug/night sight, downed combat at 21 and vitality-draining Web Spray at 31. Cannot normally ride. Web Spray does not immobilize like the inactive Webwrap grant. |
| Kobold | Night sight, underworld silent movement from 1 and later image disengagement. Nominal Dayvision adds no separate effect; no native Magic Resistance is assigned. |
| Planetbound Illithid | High shrug and both astral routes; float waits until 10 and no Blast grant exists. It uniquely retains PC Dayblind as well as sun vulnerability, so navigation/sight and recovery penalties must be evaluated separately. |
| Kuo Toa | Swamp concealment/map suppression and boat-admission benefit before waterbreath at 15; delayed lightning at 30. Sun vulnerability; native swimming access must not be mistaken for early underwater breathing. |
| Wood Elf | Earlier terrain sneak than Grey Elf, forest information and longsword bonuses, but only a 5-base shrug and no native infra/ultra. Equipment/class light support changes its practical exploration gap. |
| Firbolg | Opener/doors and full forest map information from 1. Magic Vulnerability and absence of racial dark-vision bits create different constraints from the dwarf/elf packages; Forest Sight is not night sight. |
| Tiefling | Both vision bits, fire protection and modest shrug immediately, without the sun penalty assigned to many evil races. It has no native fire attack, darkness globe or active racial command. |

### Class overlap and build dependence

The following shared class grants can make a racial ability redundant, earlier,
or relevant on a class that otherwise lacks it. Class/race eligibility is a
separate gate; this list does not assert every theoretical pairing is creatable.

- **Outdoor Sneak:** Ranger 1. **Forest Sight:** Druid/Blighter 1.
- **Fly:** Ethermancer 1, Air Conjurer 30. **Waterbreath:** Water Conjurer 30.
- **Magic Resistance:** Avenger 1; the resulting racial shrug base is still
  race-based, not a special Avenger rating. **Eyeless:** Avenger/Dreadlord 1.
- **Vampiric Touch:** Antipaladin 1. **Battle Frenzy:** Dragoon 16.
- **Hammer Master:** Ragelord Berserker 31. **Perception:** Bounty Mercenary 31.
- **Seadog:** Swashbuckler Warrior 30. **Call of the Grave:** Deathlord 30,
  while the learned skill is another access route.
- **Fireshield:** Fire Conjurer/Pyrokinetic 30. **Fire Protection:** those two,
  Water Conjurer/Mentalist Summoner 30 and Flame Reaver 31.
- **Cold Protection:** Water Conjurer/Mentalist Summoner 30.
- **Regeneration:** Naturalist Summoner 30 and Water Conjurer 36.
- **Stone Skin:** Earth Conjurer/Naturalist Summoner 30 and Earth Reaver 36.

Duplicate innate ownership does not double a boolean or the same named proc.
However, the **class can change the payload**: regeneration multiplier, stone
charges, Haste duration, vamp fraction, summon variant and travel lag. A
learned spell can also provide a similar state with different duration/cost,
and racial access does not waive inner class checks.
[Class grants](../../../src/classes/innates.c#L882),
[class/race configuration](../../content/classes_and_races.txt).

## 11. Active-innate cost and reuse index

All entries assume the committed settings and one use unless otherwise noted.
Durations of the resulting power appear in the detailed sections above.
“Default” means 720s from the first use; validation can occur before or after
consumption as described there. This table covers all **34 active innate IDs**
in the PC racial roster.

| Active innate | Reuse | Explicit actor lag | Additional cost/important dependency |
|---|---|---|---|
| Levitate | Default | 4s, including its refusals | Already floating does not spend use |
| Darkness | Default | 4s, including tired refusal | Existing light/dark room can absorb the attempt |
| Faerie Fire | No timer | 4s | Existing Faerie Fire does not stack |
| Underdark Invisibility | Default | None in handler | Underground activation; bad terrain spends use |
| Strength | Default | 4s on success | Existing Strength spends use without replacement |
| Doorbash | No timer | 8s if alive | Self damage; successful entry |
| Summon Horde | Default | None in handler | Delayed room/prototype/count checks |
| Bodyslam | No innate timer | Usually 12s; branch-specific | 30 vitality; opening/size/takedown checks |
| Ogre Roar | Default | None in handler | Most failures occur after spending use |
| Blast | Default | None in handler | Random/paralysis checks; shopkeeper waste |
| Astral Shift | Default | 4s on dispatch or in-fight rejection | PvP and inner travel checks |
| Prime Shift | Default | 4s on success or in-fight rejection | Astral zone; destination selection |
| Bite | 12s supplied by helper | Venom 4s; Vampire 12s | Actual helper key is `innate.timer.bite` |
| Doorkick | No timer | 8s if alive | Self damage; temporary crossing and return |
| Stampede | 60s supplied | 4s with 2+ hits, otherwise 0 | Footing, front line, room/area checks |
| Charge | 12s after a hit via skill tag | 8s after target admission | 30 vitality; low-ceiling knockout/terrain |
| Enlarge | Default | 4s | Existing enlarge/titan form can waste use |
| Project Image | No timer | 4s after load | Template mobile 250 |
| Fireshield | No timer | 4s | Elemental-shield exclusivity |
| Firestorm | No timer | 16s if actor remains | Area target selection and defenses |
| Burrow | Default | 4s | Already hidden rejects before use |
| Globe of Darkness | Default | 4s | Mage-flame/existing-globe conflict |
| Disappear | No timer | 4s | Some fight in the room |
| Throw Lightning | Default | 4s when scheduled | Combat required after use spent; current foe at 8s |
| Stone Skin | 300s supplied | 12s | Skin conflicts; class-dependent charges |
| Phantasmal Form | Default | 4s to activate | Existing form toggles off before timer |
| Shade Movement | Default | None in handler | Light/command rules |
| Shadow Door | Default | 9s normally, 1s Shadow, 3s Air | Named visible target; travel rules |
| Battle Rage | Default | 8s | Haste/Slow and class duration rules |
| Summon Warg | Default | None in handler | One mount; delayed terrain/prototype checks |
| Summon Totem | No timer | None in handler | 4s event delay; item grant/equip requirement |
| Call of the Grave | 240s via skill tag | 8s | Footing and delayed summon; own despawn |
| Web Spray | 300s supplied | 4s | Freedom/Evade/chance can consume the attempt |
| Reflection | 300s configured | 4s | Titan refusal happens before use/lag |

The checked-in **`innate.timer.secs.bite=12` is not the key read by the Bite
helper**, which reads `innate.timer.bite` (absent, fallback 12) and passes that
duration explicitly. The numerical result currently agrees, but changing only
the `.secs.bite` property would not tune this path.
[Bite helper](../../../src/classes/innates.c#L2211),
[timer override rule](../../../src/classes/innates.c#L1117),
[committed key](../../../lib/duris.properties#L2044).

## 12. Lifecycle, boundaries and interpretation

Racial grants are looked up from code and current level/race, rather than
consumed as a permanent trained resource. Passive flags are reasserted during
affect recalculation and login/mobile setup. Existing active affects, equipped
summoned objects and created followers have their **own lifetimes**; changing
race is not a universal cleanup of every previously created effect. The old
`get_level_from_innate()` helper uses different historical rules, but no active
caller was found; command access is controlled by `innate_unlock_level`.
[Lookup](../../../src/classes/innates.c#L408),
[passive bits](../../../src/magic/affects.c#L740),
[unused historical helper](../../../src/classes/innates.c#L6753).

Generic innate cooldowns are short, hidden, nondispellable, non-applying affects
with the innate ID in `location` and remaining-use counter in `modifier`.
They are **not flagged NOSAVE or OFFLINE**. Player snapshot capture records
eligible affects and short-event time remaining; materialization recreates
them through the affect machinery. The ordinary offline-advance loop explicitly
requires OFFLINE. Therefore logging out is not a fresh-use reset and the
generic timer does not explicitly opt into counting offline elapsed time.
This is a source-level persistence contract; no live logout/relogin journey
was run for this document.
[Timer creation](../../../src/classes/innates.c#L1227),
[snapshot](../../../src/player/player_snapshot_capture.c#L300),
[materialization](../../../src/player/player_load_materialize.c#L678),
[offline gate](../../../src/account/nanny.c#L1773).

Hatred deliberately uses NOSAVE/NODISPEL affects and a rearmed watcher rather
than saving its unlimited speed bonus. Web Spray uses an affect-owned periodic
event with restore/remove hooks. Pet control, explicit summon despawn and
summoned-item ownership are separate from the actor's innate cooldown. Neither
an indefinite charm nor a completed item grant proves that a source spell's
rest or all its effects are indefinite.

Halfling's **bare-feet +6 movement regeneration**, its configured movement
bonus, Human's stat bonus, native Barbarian cold reduction, Drow's native free
dodge, native immaterial/undead status and race-only equipment anatomy are
examples of **adjacent racial rules**, not additional entries among the 78.
They must still be considered in a whole-race balance decision. In particular,
the cold predicate separately adds **-40% for native Barbarian**: its level-31
protection adds -15% inside the same predicate, changing that isolated factor
from .60 to .45 before other modifiers. Crediting all 55% to Protection from
Cold would overstate the innate's own benefit.
[Bare feet](../../../src/classes/innates.c#L5746),
[login watcher](../../../src/account/nanny.c#L1500),
[native cold branch](../../../src/combat/dam_mods.c#L488),
[native Drow dodge](../../../src/combat/fight.c#L9261),
[stat reference](race-stats.md).

Important source mismatches to retain when balancing or updating player help:

- Dayvision is currently inert; Leap's real race gate disagrees with its listed
  unlock and admits Harpy too.
- Warg belongs to Orc, not its nearby Goblin comment. Storm Giant's commented
  grants are not active. Several old help/themes describe removed innates.
- Gaze is not a current PC Vampire innate; the heal/charm block after
  `vampire_bite(...); return;` is unreachable. The live Bite variant does not
  inherit those legacy rewards.
- Eyeless/Dayblind, sun burn/HP recovery/mana recovery, and “outdoor” terrain
  sneak are different predicates, with different exception sets.
- Rrakkma's shrug cap is five other holders; its AC loop has no five-holder cap.
  Warcaller's Fury uses the victim's other group PCs and its own holder count.
- Bite's cooldown property spelling, Ogre Roar's mixed-subject worst outcome,
  Faerie Fire's caster-concealment guard, Blast's save sign and the Troll-burn
  refresh field/event distinction are observable implementation details, not
  safe assumptions from an ability's name or comment.
- A generic “magic resistance” name can mean innate shrug, a WIS-derived
  damage modifier or equipment defenses elsewhere. An unshruggable delivery
  can still face other defenses; a shrugged spell never reaches later absorb.

These observations document present behavior. They do not establish that
every unusual rule is unintended or authorize a gameplay change. Fix/design
work should preserve the owning action's actual units, subjects, defenses,
content reachability and persistence rules, with a focused regression for any
changed behavior.

## 13. Evidence, verification and limits

The review enumerated the active PC-range assignments independently of source
comment headings, matched innate IDs to names/handlers, followed direct checks
and derived macros/affect bits, read the active command and called-spell paths,
and compared numeric settings with `lib/duris.properties`. The document's
37-row roster was also parsed back into an independent expected matrix and
executed against extracted **production `assign_innates` and `has_innate`**
under ASan/UBSan: **37 races, 188 grants, all 184 global innate IDs, levels
1..56, 381,248 race/innate/level comparisons**. All passed. This checks grant
coverage and level boundaries, not every gameplay outcome.

Existing focused checks passed in this checkout:

- `tests/async/test_innate_specialization.py`: lookup, invalid specialization,
  restore and snapshot behavior under sanitizers.
- `tests/async/test_race_rebalance.py`: current stat/innate rebalance contracts,
  Reflection grants and removal of Troll Groundfighting.
- `tests/async/test_race_innate_help_sync.py`: active assignments and generated
  race help remain synchronized, including unresolved-assignment rejection.
- `tests/async/test_innate_reflection.py`: real dispatch, race/level grants,
  self target, configured rest and Titan rejection.
- `tests/async/test_innate_hatred.py`: matching, visibility, eligibility,
  normalization, scheduler ownership, timing and serialization.
- `tests/async/test_innate_plane_shift.py`: full-name/summon routing,
  specialization access, lag and class Plane Shift reuse.
- `tests/async/test_web_spray.py`: targeting, rest/defenses, refresh,
  PC/NPC restoration, mounted movement escape and cleanup.
- `tests/async/test_stampede.py`: command admission, rest, engaged targets,
  back rank and room-change behavior.
- `tests/async/test_shift_prime.py`: 1,056 replacement-zone landings across
  three shared races, fixed/race-specific lists, missing destinations/anchor,
  combat, Astral restriction, rest and movement failure.
- `tests/async/test_ability_innates_1.py` and
  `tests/async/test_ability_innates_2.py`: extracted production numbers/facts,
  seeded RNG compatibility, source bindings and presentation across viewers.

The local review manifest/probe/logs are ignored artifacts under
`bin/tests/race-innates-review/`. Documentation links, roster counts, full
78-ID coverage and whitespace were checked. No C/C++ or balance setting was
changed, so no full server build was needed. No server was started/stopped,
no production action performed, and no commit/push is part of this analysis.

**Limits:** these are static source and focused executable findings. Deployed
properties, live SQL object/mobile prototypes, actual special-proc assignments,
equipment prevalence, race populations, PvP outcomes and every live journey
were not measured. Legacy area files cited here show checked-in templates,
not proof of the running database's exact objects. Full server interactions,
runtime overrides, later source changes and uncommon class/form combinations
can change the practical result; use the owning source and focused in-game
journey before changing balance. “All effects” here means the traced implemented
innate mechanics and their downstream rule families, including inactive and
conditional distinctions, rather than a claim to enumerate every possible
encounter, item build or emergent player strategy.
