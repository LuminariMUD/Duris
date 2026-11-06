# Named zone sets: effect usage and unused candidates

Status: baseline effect inventory for [issue #706](https://github.com/LuminariMUD/Duris/issues/706). All 115 baseline definitions are retained; the integrated catalog adds 183 reviewed areas, totaling 298 rows, 389 tiers and 106 effect IDs. Validation and release status are recorded in [PR #748](https://github.com/LuminariMUD/Duris/pull/748); production publication is pending.
Date: 2026-11-06.
Inspected `master`: `2d2a7d48dea91dbe773701790239db76f59806c2`.

Implementation entry point: [end-to-end plan](named-zone-set-implementation-plan.md).
Proposed zone homes: [complete assignment plan](named-zone-set-first-pass-assignments.md).

## What this document counts

A named set is matching random equipment with the same virtual zone origin.
Unresolved historical tags retain their separate HP-only legacy groups.
Its ordinary HP bonus is separate from its configured spell bonuses: every
piece after the second adds 5 maximum HP. This document inventories the extra
effects that can help us choose bonuses for uncovered zones.

**The counts below describe the original baseline.** Final home counts for the
qualified pool appear in the assignment document, including the 79 wider-review
additions. No original effect or threshold was retuned.

**Zone count means the number of distinct loaded zones whose set definition
uses that effect ID.** A three-piece requirement counts as one zone, not three
uses. Different IDs that call the same spell function remain separate, so
aliases are visible. These are configured counts, not live-player usage,
drop rates, or a promise that every existing item currently activates correctly.

| Measure | Count |
|---|---:|
| Active set-table zone definitions, before resolving the world | 117 |
| Definitions that resolve to loaded zones | 115 |
| Distinct effect IDs used by those 115 zones | 64 |
| Zone/effect assignments across loaded zones | 206 |
| Zone/effect assignments including stale definitions | 209 |
| Unused candidate IDs in this document | 42 |

The two stale definitions are kept outside the main count:

| Unresolved zone ID | Definition | Addition if counting all table rows |
|---|---|---|
| 30 | Concealment at 3 pieces; Haste at 5 | +1 Concealment zone and +1 Haste zone |
| 250 | Fire Ward at 2 pieces | +1 Fire Ward zone |

Four baseline zones had set definitions but plain titles that blocked fresh
zone-named kill drops: Lair of the Gibberling King (#87), Crystalspyre Mountains
(#370), Taliccicopiid (#676), and The Temple of the Sun (#824). Their authored
titles now carry color codes after source review of their entrances and repeatable
encounters. They retain their existing effects/thresholds and remain in the 115
configured rows. Regeneration and deployment are required for a running game to
use those title fixes. See the [eligibility evidence](named-zone-set-first-pass-assignments.md#existing-plain-title-set-areas).

Sources: [set definitions](../../src/item/named_sets.c),
[active area registry](../../areas/AREA),
[naming eligibility](../../src/item/random_equipment.c), and
[`random_set()` / `check_zone_spells()` / `apply_zone_spell()`](../../src/specs/specs.object.c).

## Effects already used by current zones

Sorted by zone count, then name. The threshold column shows how many zones use
each piece requirement: `3 pieces × 12` means twelve zones unlock that effect
at three matching pieces. Zone names are included so the counts can be reviewed.

| Effect (game ID) | Zone count | Piece thresholds across those zones | Current zones |
|---|---:|---|---|
| [Endurance](../../src/classes/skills.c#L727) (#355) | 22 | 3 pieces × 5; 4 pieces × 2; 5 pieces × 8; 6 pieces × 7 | The Lizardman Swamps of Clavikord (#60); Court of the Muse (#67); The Outcasts Tower (#113); Pine Hollow (#160); Woodseer (#165); The Forest City of Aravne (#215); The Halfcut Hills (#270); Pharr Valley Swamp (#285); Strathor Valley of the Storm Giants (#308); Arachdrathos Wilderness (#360); Crystalspyre Mountains (#370); Nax (#377); Village of Werrun (#383); Ugta (#391); Forest of Mir (#419); Charing (#450); Taliccicopiid (#676); The Town of Moregeeth (#700); Rift Valley Jungle (#800); Arcium, the Plagued Kingdom (#857); Shady Grove (#975); Tharnadia - City of Humans (#1325) |
| [Armor](../../src/classes/skills.c#L743) (#1) | 15 | 2 pieces × 3; 3 pieces × 12 | Kobold Settlement (#14); Valley of Crushk (#20); The Town of Breale (#26); Ako Village (#37); Fort Marigot (#53); The Lizardman Swamps of Clavikord (#60); Khildarak Stronghold (#170); Krethik Keep (#200); Pharr Valley Swamp (#285); Harrow -The Gnome Village (#294); Nizari (#400); The Town of Moregeeth (#700); Kimordril (#955); Shady Grove (#975); Tharnadia - City of Humans (#1325) |
| [Bless](../../src/classes/skills.c#L1366) (#3) | 13 | 2 pieces × 3; 3 pieces × 10 | Kobold Settlement (#14); Valley of Crushk (#20); The Town of Breale (#26); Ako Village (#37); Fort Marigot (#53); The Lizardman Swamps of Clavikord (#60); Woodseer (#165); Khildarak Stronghold (#170); Pharr Valley Swamp (#285); Nizari (#400); The Keep of Evil (#448); Rift Valley Jungle (#800); Kimordril (#955) |
| [Stone Skin](../../src/classes/skills.c#L1991) (#36) | 13 | 5 pieces × 3; 6 pieces × 9; 7 pieces × 1 | Dragonnia (#68); The Prisons of Carthapia (#73); The Ethereal Plane (#124); The Citadel (#130); New Cave city (#151); Ny'Neth (#229); Plane of Earth (#238); The Kingdom of Torg (#289); Arachdrathos Guilds (#367); Du'Maathe Castle (#371); The Fields Between (#710); The Obsidian Citadel (#756); Jotunheim (#960) |
| [Barkskin](../../src/classes/skills.c#L4259) (#141) | 9 | 2 pieces × 1; 3 pieces × 8 | Court of the Muse (#67); Woodseer (#165); Shairak and Smokeveil Forest (#202); The Forest City of Aravne (#215); Vast Hidden Grove (#306); Pharr Valley (#402); Forest of Mir (#419); Charing (#450); Rift Valley Jungle (#800) |
| [Fly](../../src/classes/skills.c#L2362) (#84) | 8 | 2 pieces × 1; 3 pieces × 2; 4 pieces × 3; 5 pieces × 2 | The Mountain of the Banished (#91); Ny'Neth's Stronghold (#230); Plane of Air (#244); The Mountain Settlement of the Harpies (#311); The Plane of Avernus (#320); The Ruins of Tharnadia's Old Quarter (#662); Rogue Plains (#758); Jotunheim (#960) |
| [Protection From Undead](../../src/classes/skills.c#L4220) (#136) | 7 | 3 pieces × 6; 4 pieces × 1 | Mazzolin (#213); Killing Fields (#333); The Bloody Plains (#335); Domain of Lost Souls (#368); Shadamehr Keep (#412); The Obsidian Citadel (#756); The Undead Outpost (#987) |
| [Spirit Armor](../../src/classes/skills.c#L2936) (#192) | 7 | 2 pieces × 4; 3 pieces × 2; 4 pieces × 1 | Vargan (#21); Sarmiz'Duul (#94); Village of Split Shield (#103); Pragtog's Domain (#106); Faang (#152); Ugta (#391); Arcium, the Plagued Kingdom (#857) |
| [Invisibility](../../src/classes/skills.c#L1851) (#189) | 6 | 3 pieces × 1; 4 pieces × 1; 5 pieces × 2; 6 pieces × 1; 7 pieces × 1 | The Ethereal Plane (#124); The Transparent Tower (#162); Drifting Realm (#313); Sea Kingdom (#315); Apocalypse Castle (#345); Forest of Mir (#419) |
| [Spirit Ward](../../src/classes/skills.c#L3011) (#220) | 6 | 3 pieces × 2; 4 pieces × 4 | Lair of the Gibberling King (#87); Sarmiz'Duul (#94); Village of Split Shield (#103); Pragtog's Domain (#106); Faang (#152); Arcium, the Plagued Kingdom (#857) |
| [Regeneration](../../src/classes/skills.c#L642) (#294) | 5 | 2 pieces × 1; 3 pieces × 1; 4 pieces × 1; 5 pieces × 1; 6 pieces × 1 | The Troll Hills (#18); The Mountain of the Banished (#91); The Outcasts Tower (#113); Swamp (#260); The Lair of the Swamp Troll King (#261) |
| [Vitality](../../src/classes/skills.c#L1693) (#56) | 5 | 4 pieces × 1; 5 pieces × 1; 6 pieces × 3 | Krethik Keep (#200); Shadamehr Keep (#412); The Keep of Evil (#448); Father Tel's Holy Cloister (#671); The Temple of the Sun (#824) |
| [Globe Of Invulnerability](../../src/classes/skills.c#L3917) (#144) | 4 | 3 pieces × 2; 4 pieces × 1; 5 pieces × 1 | Dragonnia (#68); Ny'Neth's Stronghold (#230); Fort Boyard (#381); Sevenoaks (#386) |
| [Soulshield](../../src/classes/skills.c#L2662) (#188) | 4 | 3 pieces × 1; 4 pieces × 1; 5 pieces × 2 | Orrak (#90); Domain of Lost Souls (#368); Shadamehr Keep (#412); The Keep of Evil (#448) |
| [Strength](../../src/classes/skills.c#L2037) (#39) | 4 | 2 pieces × 1; 3 pieces × 1; 4 pieces × 1; 5 pieces × 1 | Tower of High Sorcery (#93); Khildarak Stronghold (#170); Clan Stoutdorf Settlement (#342); Kimordril (#955) |
| [Water Breathing](../../src/classes/skills.c#L1571) (#85) | 4 | 2 pieces × 2; 3 pieces × 2 | Storm Port (#224); Storm Port Stronghold (#226); Plane of Water (#232); Sea Kingdom (#315) |
| [Cold Ward](../../src/classes/skills.c#L2877) (#232) | 3 | 3 pieces × 3 | Myconid Mushroom Forest (#23); Ice Tower (#318); Sevenoaks (#386) |
| [Flesh Armor](../../src/classes/skills.c#L956) (#179) | 3 | 3 pieces × 2; 6 pieces × 1 | Arena of the Elder Brain (#112); The Great Shaboath (#328); Ixarkon (#964) |
| [Haste](../../src/classes/skills.c#L2163) (#41) | 3 | 4 pieces × 1; 5 pieces × 2 | Lair of the Gibberling King (#87); Desolate (#222); Vella's Bordello (#936) |
| [Intellect Fortress](../../src/classes/skills.c#L974) (#182) | 3 | 4 pieces × 1; 5 pieces × 1; 6 pieces × 1 | Arena of the Elder Brain (#112); The Great Shaboath (#328); Ixarkon (#964) |
| [Pass Without Trace](../../src/classes/skills.c#L2079) (#280) | 3 | 4 pieces × 1; 7 pieces × 1; 9 pieces × 1 | The Forgotten Mansion (#35); The Outcasts Tower (#113); The Forest City of Aravne (#215) |
| [Song Of Dragons](../../src/classes/skills.c#L3833) (#1529) | 3 | 9 pieces × 3 | Dragonnia (#68); Tiamat (#196); Bahamut's Palace (#257) |
| [True Seeing](../../src/classes/skills.c#L2700) (#236) | 3 | 4 pieces × 1; 6 pieces × 2 | Zalkapfaan, City of the Headless Horde (#27); The Mountain of the Banished (#91); The Plane of Avernus (#320) |
| [Biofeedback](../../src/classes/skills.c#L857) (#161) | 2 | 5 pieces × 1; 7 pieces × 1 | The Astral Plane (#197); Ny'Neth's Stronghold Continued (#387) |
| [Concealment](../../src/classes/skills.c#L1860) (#29) | 2 | 6 pieces × 2 | Clan Stoutdorf Settlement (#342); Arachdrathos Wilderness (#360) |
| [Detect Invisibility](../../src/classes/skills.c#L1709) (#19) | 2 | 4 pieces × 1; 5 pieces × 1 | Ny'Neth's Stronghold (#230); Apocalypse Castle (#345) |
| [Detect Magic](../../src/classes/skills.c#L1734) (#92) | 2 | 3 pieces × 2 | Moonshae Island (#262); Harrow -The Gnome Village (#294) |
| [Fire Ward](../../src/classes/skills.c#L2882) (#233) | 2 | 2 pieces × 1; 4 pieces × 1 | Myconid Mushroom Forest (#23); Plane of Fire (#254) |
| [Greater Spirit Sight](../../src/classes/skills.c#L3028) (#225) | 2 | 3 pieces × 2 | Tiamat (#196); Bahamut's Palace (#257) |
| [Greater Spirit Ward](../../src/classes/skills.c#L3032) (#227) | 2 | 6 pieces × 2 | Tiamat (#196); Bahamut's Palace (#257) |
| [Minor Globe Of Invulnerability](../../src/classes/skills.c#L1383) (#61) | 2 | 4 pieces × 1; 5 pieces × 1 | Tower of High Sorcery (#93); Mazzolin (#213) |
| [Pantherspeed](../../src/classes/skills.c#L2777) (#201) | 2 | 6 pieces × 2 | Sarmiz'Duul (#94); Pits of Cerberus (#220) |
| [Protection From Cold](../../src/classes/skills.c#L2308) (#97) | 2 | 3 pieces × 2 | The Elemental Groves (#38); Ugta (#391) |
| [Stornogs Spheres](../../src/classes/skills.c#L2107) (#286) | 2 | 6 pieces × 1; 8 pieces × 1 | Pit of Dragons (#159); Sea Kingdom (#315) |
| [Vampiric Touch](../../src/classes/skills.c#L4206) (#134) | 2 | 6 pieces × 2 | The Forgotten Mansion (#35); Nakral's Crypt (#143) |
| [Agility](../../src/classes/skills.c#L2053) (#584) | 1 | 2 pieces × 1 | Tower of High Sorcery (#93) |
| [Battle Ecstasy](../../src/classes/skills.c#L2689) (#292) | 1 | 6 pieces × 1 | The Caverns of Armageddon (#133) |
| [Blur](../../src/classes/skills.c#L2075) (#263) | 1 | 6 pieces × 1 | The Bronze Citadel (#324) |
| [Chaos Shield](../../src/classes/skills.c#L3477) (#560) | 1 | 6 pieces × 1 | Lost Temple of Tikitzopl (#441) |
| [Coldshield](../../src/classes/skills.c#L2648) (#131) | 1 | 5 pieces × 1 | Ice Tower (#318) |
| [Conjure Elemental](../../src/classes/skills.c#L2220) (#78) | 1 | 6 pieces × 1 | Caves of Mt. Skelenak (#40) |
| [Dazzle](../../src/classes/skills.c#L2071) (#293) | 1 | 4 pieces × 1 | The Bronze Citadel (#324) |
| [Elephantstrength](../../src/classes/skills.c#L2817) (#221) | 1 | 4 pieces × 1 | Faang (#152) |
| [Enhance Agility](../../src/classes/skills.c#L944) (#177) | 1 | 2 pieces × 1 | Arena of the Elder Brain (#112) |
| [Enhance Strength](../../src/classes/skills.c#L932) (#175) | 1 | 3 pieces × 1 | The Kingdom of Torg (#289) |
| [Epic Strength](../../src/classes/epic_skills.c#L333) (#1251) | 1 | 3 pieces × 1 | Zalkapfaan, City of the Headless Horde (#27) |
| [Faerie Sight](../../src/classes/skills.c#L3260) (#473) | 1 | 2 pieces × 1 | Faerie Realm (#140) |
| [Farsee](../../src/classes/skills.c#L1577) (#53) | 1 | 3 pieces × 1 | Moonshae Island (#262) |
| [Fireshield](../../src/classes/skills.c#L2416) (#108) | 1 | 4 pieces × 1 | Temple of Flames (#183) |
| [Infernal Fury](../../src/classes/skills.c#L4979) (#654) | 1 | 8 pieces × 1 | The Plane of Avernus (#320) |
| [Invigorate](../../src/classes/skills.c#L1528) (#581) | 1 | 4 pieces × 1 | Fort Marigot (#53) |
| [Levitate](../../src/classes/skills.c#L2353) (#83) | 1 | 5 pieces × 1 | Moonshae Island (#262) |
| [Lionrage](../../src/classes/skills.c#L2812) (#215) | 1 | 6 pieces × 1 | Pits of Cerberus (#220) |
| [Negative Energy Barrier](../../src/classes/skills.c#L1771) (#333) | 1 | 3 pieces × 1 | Negative Material Plane (#266) |
| [Negative Feedback Barrier](../../src/classes/skills.c#L3349) (#593) | 1 | 5 pieces × 1 | Negative Material Plane (#266) |
| [Protection From Fire](../../src/classes/skills.c#L2301) (#96) | 1 | 3 pieces × 1 | The Elemental Groves (#38) |
| [Protection From Lightning](../../src/classes/skills.c#L2347) (#98) | 1 | 3 pieces × 1 | The Elemental Groves (#38) |
| [Protection From Living](../../src/classes/skills.c#L2317) (#318) | 1 | 3 pieces × 1 | Vella's Bordello (#936) |
| [Ravenflight](../../src/classes/skills.c#L2822) (#238) | 1 | 4 pieces × 1 | The High Moor Forest (#191) |
| [Shadow Shield](../../src/classes/skills.c#L3191) (#411) | 1 | 6 pieces × 1 | Myrloch Vale (#264) |
| [Spirit Sight](../../src/classes/skills.c#L2972) (#208) | 1 | 5 pieces × 1 | Myconid Mushroom Forest (#23) |
| [Thornskin](../../src/classes/skills.c#L4264) (#625) | 1 | 4 pieces × 1 | Pine Hollow (#160) |
| [Thryms Icerazor](../../src/classes/skills.c#L3105) (#393) | 1 | 4 pieces × 1 | Quintaragon Castle (#24) |
| [Vampiric Trance](../../src/classes/skills.c#L4172) (#284) | 1 | 8 pieces × 1 | Castle Ravenloft (#583) |

## Unused effects that could become set bonuses

**Every entry below has a current zone count of 0**, including the two stale
table rows. The catalog retains **42 spell candidates for an underpowered
first pass**.

This deliberately conservative screen keeps ordinary stat/attack bonuses,
armor and saves, narrow protections, and basic senses/utility. It defers speed
boosts, pass-door/access powers, transformations, broad immunities and protection
packages, maximum-stat and large HP packages, regeneration, weapon/combat procs,
progression rewards, and epic-stat grants. These choices can be reconsidered
in a later balance pass; they are omitted from the candidate lists here.

Candidates requiring extra targeting, new cooldown handling, different-effect-ID
cleanup, group/pet/object lifecycles, or custom adapters also remain omitted.
Existing class, race, alignment, equipment, terrain, and stacking restrictions
still apply to the retained effects.

These are source-level candidates; their power and piece thresholds still need
to be chosen for each zone. Effect-name links point to their implementations.

### How to read the integration notes

- **Wearer buff:** an implemented character effect with the existing spell-call
  interface. Keep its existing caps, prerequisites, mutual exclusions, and
  dispel behavior.
- **Conditional:** the benefit depends on an existing requirement, such as class
  or alignment. That restriction remains in force.

The generic handler calls a spell with the wearer as both caster and target,
null text/object arguments, and call type `0`. Most use a level derived from
the number of matching pieces.

| Candidate group | Unused IDs |
|---|---:|
| Stats, attacks, and movement | 14 |
| Armor, saves, and protection | 11 |
| Senses and utility | 15 |
| Class and alignment bonuses | 2 |

### Stats, attacks, and movement

| Effect (game ID; all have zone count 0) | Benefit in plain language | Integration notes |
|---|---|---|
| [Adrenaline Control](../../src/classes/psionics.c#L412) (#157) | Strength and Constitution. | Wearer buff. |
| [Battletide](../../src/magic/magic.c#L16594) (#395) | Attack accuracy and damage. | Wearer buff. |
| [Combat Mind](../../src/classes/psionics.c#L1094) (#163) | Attack accuracy and damage. | Wearer buff. |
| [Dexterity](../../src/magic/magic.c#L11563) (#73) | Dexterity. | Wearer buff. |
| [Divine Fury](../../src/magic/magic.c#L22267) (#310) | Attack accuracy and damage. | Wearer buff. |
| [Enhance Constitution](../../src/classes/psionics.c#L2650) (#178) | Enhanced Constitution. | Wearer buff. |
| [Enhance Dexterity](../../src/classes/psionics.c#L2564) (#176) | Enhanced Dexterity. | Wearer buff. |
| [Fortitude](../../src/magic/magic.c#L6345) (#348) | Constitution. | Amount depends on the caster's existing rules. |
| [Lifelust](../../src/magic/magic.c#L7776) (#321) | Attack accuracy and damage. | Wearer buff. |
| [Pulchritude](../../src/magic/magic.c#L8075) (#347) | Charisma. | Wearer buff. |
| [Serendipity](../../src/magic/magic.c#L8284) (#352) | Luck. | Wearer buff. |
| [Vapor Strike](../../src/classes/ethermancer.c#L1134) (#467) | Attack accuracy. | Wearer buff. |
| [Warring Zeal](../../src/magic/magic.c#L25432) (#680) | Attack accuracy. | Wearer buff. |
| [Wolfspeed](../../src/magic/smagic.c#L2683) (#193) | Maximum movement/vitality pool. | Wearer buff. |

### Armor, saves, and protection

| Effect (game ID; all have zone count 0) | Benefit in plain language | Integration notes |
|---|---|---|
| [Displacement](../../src/classes/psionics.c#L2206) (#169) | Armor-class protection. | Wearer buff. |
| [Energy Containment](../../src/classes/psionics.c#L2405) (#173) | Improved spell saves. | Wearer buff. |
| [Enhance Armor](../../src/classes/psionics.c#L2459) (#174) | Armor-class improvement. | Wearer buff. |
| [Phantom Armor](../../src/classes/sillusionist.c#L131) (#400) | Armor-class protection. | Uses the shared armor bit; preserve armor exclusions. |
| [Protection From Acid](../../src/magic/magic.c#L21936) (#105) | Acid protection. | Wearer buff. |
| [Protection From Animals](../../src/magic/magic.c#L21864) (#383) | Protection from animals. | Wearer buff. |
| [Protection From Evil](../../src/magic/magic.c#L10975) (#34) | Protection from evil. | Wearer buff. |
| [Protection From Gas](../../src/magic/magic.c#L21917) (#104) | Gas protection. | Wearer buff. |
| [Protection From Good](../../src/magic/magic.c#L11004) (#81) | Protection from good. | Wearer buff. |
| [Slow Poison](../../src/magic/magic.c#L17814) (#130) | Slows poison. | Wearer buff. |
| [Vapor Armor](../../src/classes/ethermancer.c#L104) (#452) | Armor-class protection. | Uses the shared armor bit; preserve armor exclusions. |

### Senses and utility

| Effect (game ID; all have zone count 0) | Benefit in plain language | Integration notes |
|---|---|---|
| [Comprehend Languages](../../src/magic/magic.c#L17843) (#132) | Language comprehension. | Wearer buff. |
| [Detect Evil](../../src/magic/magic.c#L9246) (#90) | Detect evil. | Wearer buff. |
| [Detect Good](../../src/magic/magic.c#L9283) (#91) | Detect good. | Wearer buff. |
| [Detect Illusion](../../src/classes/sillusionist.c#L1797) (#414) | Detect illusion and invisible targets. | Wearer buff. |
| [Globe Of Darkness](../../src/magic/magic.c#L17667) (#302) | A carried sphere of darkness. | Conditional: excludes light effects; preserve character/room-light recalculation. |
| [Hawkvision](../../src/magic/smagic.c#L3281) (#204) | Hawkvision. | Wearer buff. |
| [Holy Light](../../src/magic/magic.c#L17597) (#615) | A carried holy light. | Conditional: shares the Mage Flame light bit and excludes Globe of Darkness. |
| [Infravision](../../src/magic/magic.c#L22089) (#106) | See with infravision. | Wearer buff. |
| [Lodestone Vision](../../src/magic/magic.c#L12484) (#617) | Mineral detection. | Wearer buff. |
| [Mage Flame](../../src/magic/magic.c#L17626) (#297) | A carried magical light. | Conditional: excludes Globe of Darkness; preserve character/room-light recalculation. |
| [Scent Of The Bloodhound](../../src/magic/smagic.c#L2353) (#517) | Bloodhound tracking/scent effect. | Wearer buff. |
| [Sense Follower](../../src/magic/magic.c#L24629) (#279) | Sense followers. | Wearer buff. |
| [Sense Holiness](../../src/magic/magic.c#L7067) (#316) | Sense holy auras. | Wearer buff. |
| [Sense Life](../../src/magic/magic.c#L12385) (#44) | Sense living creatures. | Wearer buff. |
| [Sense Spirit](../../src/magic/smagic.c#L4244) (#211) | Sense spirits/life. | Wearer buff. |

### Class and alignment bonuses

| Effect (game ID; all have zone count 0) | Benefit in plain language | Integration notes |
|---|---|---|
| [Guardian Spirits](../../src/magic/smagic.c#L208) (#579) | 150–200 AC protection. | Conditional: requires a Shaman wearer, any specialization. Both proposed assignments require six pieces. |
| [Virtue](../../src/magic/magic.c#L6927) (#515) | Native 10% accuracy bonus against eligible targets. | Good wearers benefit against non-good targets; evil wearers against non-evil targets, including neutral targets. Neutral wearers receive no accuracy bonus. |

## Effects screened out of this wearer-bonus catalog

The source registers **1,020 distinct numeric entries**: 640 spells, 245 skills/instruments/songs, 128 internal tags, and 7 poisons. The spell/song/epic-stat screen reconciles as follows:

| Registry family | Total IDs | Used by loaded zone sets | Retained unused candidates | Extra-handling candidates omitted | Higher-impact candidates deferred | Other screened-out IDs |
|---|---:|---:|---:|---:|---:|---:|
| Spells | 640 | 62 | 42 | 107 | 66 | 363 |
| Bard songs (within skill registrations) | 19 | 1 | 0 | 5 | 0 | 13 |
| Epic-stat grants (within skill registrations) | 9 | 1 | 0 | 0 | 8 | 0 |
| **Scoped total** | **668** | **64** | **42** | **112** | **74** | **376** |

The other **352 registrations** are 217 ordinary skills/instrument entries, 128 internal tags, and 7 poisons. Their presence in the registry is not an implementation of a beneficial set effect. For example, ordinary passive skill grants such as Dodge, Parry, Toughness, or spell mastery would require an explicit skill-grant design; command buffs such as Heroism or Diamond Soul would require command-specific adapters and class/cost policy. They are not silently treated as callable spells. A separately designed skill-bonus expansion could revisit them.

All 18 unused bard songs are omitted from the candidate list: five need song-specific adapters, and the other 13 are Charming, Discord, Harmony, Storms, Chaos, Sleep, Calming, Harming, Cowardice, Forgetfulness, Peace, Dissonance, and Drifting. These affect opponents, stop/disrupt encounters, or teleport. In particular, **Harmony calls Dispel Evil against non-group targets**; its friendly-sounding name is not evidence of a wearer buff. Source: [song dispatch and implementations](../../src/classes/bard.c). Unregistered numeric constants such as Mindshield or Snatching are not additional usable songs.

The 363 unused spell IDs excluded from this catalog are accounted for below. These exclusions describe suitability for an automatic wearer bonus; they do not remove spells from the game or preclude a different, deliberately targeted item ability.

| Exclusion group | Spell IDs | Reason |
|---|---:|---|
| Item, information, and room-object actions | 15 | Creates/changes items or emits requested information; needs input and economy/world-lifecycle rules outside wearer affects. |
| Attacks, debuffs, and hostile actions | 221 | Damages, controls, reveals, drains, or disrupts other targets; belongs to a targeted/weapon-proc design rather than an automatic wearer buff. |
| Room, terrain, and exit effects | 37 | Changes rooms, sectors, walls, or exit state; requires room ownership and cleanup rather than ordinary wearer-effect cleanup. |
| Other targeted or encounter actions | 9 | Needs deliberate target/encounter selection, transfers resources, resurrects, or stops combat; not a sustained beneficial self effect. |
| Travel and anchors | 34 | Moves characters or creates travel anchors/portals; requires deliberate travel input and lifecycle rather than a recurring wearer bonus. |
| Corpse and object-dependent pet/resurrection operations | 27 | Needs an explicit corpse/object and may consume it or restore a dead player; the generic set call supplies no object. |
| Unimplemented, disabled, or placeholder | 7 | No usable implementation: empty/no-op handler, unfinished message, or an unconditional early return. |
| Permanent or special progression changes | 13 | Changes permanent stats/age, rested progression, or a character-specific race effect rather than a removable set bonus. |

**Important false positives:** Dark Compact and Summon Spirit have no active effect; Greater Flicker and Ritus Draconum are unfinished; Corpseform returns before its old implementation; Auctions Disabled and Battle Mages Aura use `do_nothing_spell`. Recharger drains another character and refuses self-targeting. Curse of Yzar is restricted to a character named Yzar. Permanent-stat spells and major rejuvenation cannot be undone just by removing gear.

<details>
<summary>Full list of screened-out spell IDs, grouped by reason</summary>

### Item, information, and room-object actions (15)

- [Continual Light](../../src/magic/magic.c#L15502) (#18).
- [Create Food](../../src/magic/magic.c#L8330) (#12).
- [Create Pond](../../src/magic/blispells.c#L1585) (#639).
- [Create Spring](../../src/magic/magic.c#L16913) (#140).
- [Create Water](../../src/magic/magic.c#L8361) (#13).
- [Darkness](../../src/magic/magic.c#L22017) (#99).
- [Divine Font](../../src/magic/magic.c#L16955) (#676).
- [Enchant Weapon](../../src/magic/magic.c#L9514) (#24).
- [Identify](../../src/magic/magic.c#L14203) (#45).
- [Item Lore](../../src/magic/magic.c#L14637) (#240).
- [Knock](../../src/magic/magic.c#L26107) (#554).
- [Mask](../../src/classes/sillusionist.c#L1259) (#408).
- [Minor Creation](../../src/magic/spells.c#L253) (#20).
- [Repair One Item](../../src/magic/magic.c#L28860) (#595).
- [Reveal True Name](../../src/magic/magic.c#L14112) (#262).

### Attacks, debuffs, and hostile actions (221)

- [Acid Blast](../../src/magic/magic.c#L18644) (#116).
- [Acid Rain](../../src/magic/blispells.c#L813) (#631).
- [Acid Stream](../../src/magic/magic.c#L18604) (#365).
- [Acidimmolate](../../src/magic/magic.c#L26353) (#428).
- [Aid Of The Heavens](../../src/magic/magic.c#L19511) (#610).
- [Alter Energy Polarity](../../src/magic/magic.c#L7035) (#331).
- [Animal Friendship](../../src/magic/magic.c#L21890) (#384).
- [Anti-Magic Ray](../../src/magic/magic.c#L821) (#363).
- [Antimatter Collision](../../src/classes/ethermancer.c#L4673) (#645).
- [Apocalypse](../../src/magic/magic.c#L25245) (#278).
- [Arcane Whirlwind](../../src/classes/ethermancer.c#L1885) (#459).
- [Arctic Blast](../../src/classes/ethermancer.c#L4812) (#646).
- [Arieks Shattering Iceball](../../src/magic/smagic.c#L1712) (#254).
- [Asphyxiate](../../src/classes/sillusionist.c#L3517) (#168).
- [Awaken Forest](../../src/magic/spells.c#L3127) (#446).
- [Awe](../../src/classes/psionics.c#L659) (#159).
- [Ballistic Attack](../../src/classes/psionics.c#L860) (#160).
- [Banish](../../src/magic/magic.c#L26928) (#495).
- [Bigbys Clenched Fist](../../src/magic/magic.c#L4417) (#77).
- [Bigbys Crushing Hand](../../src/magic/magic.c#L4497) (#285).
- [Blackmantle](../../src/magic/magic.c#L18950) (#619).
- [Blight](../../src/magic/blispells.c#L497) (#635).
- [Blindness](../../src/magic/magic.c#L8010) (#4).
- [Blood To Stone](../../src/magic/spells.c#L3361) (#451).
- [Boulder](../../src/classes/sillusionist.c#L476) (#404).
- [Burning Hands](../../src/magic/magic.c#L1121) (#5).
- [Call Lightning](../../src/magic/spells.c#L54) (#6).
- [Call Of The Wild](../../src/magic/smagic.c#L3928) (#290).
- [Cascading Elemental Beam](../../src/magic/smagic.c#L6062) (#573).
- [Cause Critical](../../src/magic/magic.c#L18569) (#115).
- [Cause Light](../../src/magic/magic.c#L18409) (#113).
- [Cause Serious](../../src/magic/magic.c#L18443) (#114).
- [Chain Lightning](../../src/magic/magic.c#L4819) (#62).
- [Channel Negative Energy](../../src/magic/magic.c#L4453) (#327).
- [Chaos Volley](../../src/magic/magic.c#L25903) (#553).
- [Chaotic Ripple](../../src/magic/magic.c#L26465) (#432).
- [Charm Animal](../../src/magic/magic.c#L22231) (#187).
- [Charm Person](../../src/magic/magic.c#L22220) (#7).
- [Chill Touch](../../src/magic/magic.c#L962) (#8).
- [Cloak Of Fear](../../src/magic/magic.c#L24887) (#283).
- [Cold Snap](../../src/classes/ethermancer.c#L449) (#472).
- [Color Spray](../../src/magic/magic.c#L686) (#109).
- [Comet](../../src/classes/ethermancer.c#L2681) (#520).
- [Command Horde](../../src/magic/magic.c#L17490) (#137).
- [Command Undead](../../src/magic/magic.c#L17434) (#129).
- [Cone Of Cold](../../src/magic/magic.c#L1279) (#10).
- [Confuse](../../src/classes/psionics.c#L3070) (#185).
- [Contagion](../../src/magic/blispells.c#L352) (#628).
- [Contain Being](../../src/magic/magic.c#L29314) (#624).
- [Control Flames](../../src/classes/psionics.c#L1280) (#489).
- [Corrosive Blast](../../src/magic/smagic.c#L930) (#229).
- [Cosmic Rift](../../src/classes/ethermancer.c#L3703) (#552).
- [Cosmic Vacuum](../../src/classes/ethermancer.c#L2770) (#528).
- [Creeping Doom](../../src/magic/magic.c#L24537) (#386).
- [Curse](../../src/magic/magic.c#L9104) (#17).
- [Cyclone](../../src/magic/magic.c#L4956) (#76).
- [Death Field](../../src/classes/psionics.c#L1670) (#166).
- [Decaying Flesh](../../src/magic/magic.c#L6249) (#620).
- [Delirium](../../src/classes/sillusionist.c#L2752) (#418).
- [Destroy Undead](../../src/magic/magic.c#L6017) (#58).
- [Detonate](../../src/classes/psionics.c#L1816) (#167).
- [Devitalize](../../src/magic/magic.c#L12873) (#324).
- [Disease](../../src/magic/magic.c#L10563) (#186).
- [Disintegrate](../../src/magic/magic.c#L18148) (#112).
- [Dispel Evil](../../src/magic/magic.c#L5674) (#22).
- [Dispel Good](../../src/magic/magic.c#L5618) (#72).
- [Dispel Invisible](../../src/magic/magic.c#L10342) (#67).
- [Dispel Lifeforce](../../src/magic/magic.c#L6986) (#330).
- [Dispel Magic](../../src/magic/magic.c#L20747) (#93).
- [Dragon](../../src/classes/sillusionist.c#L2512) (#422).
- [Dread Wave](../../src/magic/magic.c#L24140) (#424).
- [Earth Spike](../../src/magic/magic.c#L16208) (#506).
- [Earthen Grasp](../../src/magic/smagic.c#L2177) (#217).
- [Earthen Maul](../../src/magic/magic.c#L4239) (#367).
- [Earthen Rain](../../src/magic/smagic.c#L1945) (#226).
- [Earthquake](../../src/magic/magic.c#L5243) (#23).
- [Edictum Cineris](../../src/magic/magic.c#L30072) (#668).
- [Ego Blast](../../src/classes/psionics.c#L1343) (#164).
- [Ego Whip](../../src/classes/psionics.c#L2358) (#172).
- [Electrical Execution](../../src/magic/magic.c#L28579) (#577).
- [Elemental Fury](../../src/magic/smagic.c#L821) (#480).
- [Elemental Swarm](../../src/magic/magic.c#L2860) (#351).
- [Energy Drain](../../src/magic/magic.c#L1945) (#25).
- [Enervation](../../src/magic/magic.c#L1620) (#585).
- [Entangle](../../src/magic/magic.c#L16364) (#139).
- [Entropy Storm](../../src/magic/magic.c#L5155) (#337).
- [Ethereal Discharge](../../src/classes/ethermancer.c#L3001) (#531).
- [Faerie Fire](../../src/magic/magic.c#L18781) (#117).
- [Faerie Fog](../../src/magic/magic.c#L18854) (#118).
- [Fear](../../src/magic/magic.c#L14061) (#54).
- [Feeblemind](../../src/magic/magic.c#L20266) (#126).
- [Fireball](../../src/magic/magic.c#L4702) (#26).
- [Firelance](../../src/magic/blispells.c#L1351) (#637).
- [Firestorm](../../src/magic/magic.c#L5566) (#47).
- [Flame Sphere](../../src/magic/blispells.c#L214) (#626).
- [Flame Strike](../../src/magic/magic.c#L5770) (#21).
- [Flameburst](../../src/magic/smagic.c#L1136) (#195).
- [Forked Lightning](../../src/classes/ethermancer.c#L1205) (#460).
- [Frost Beam](../../src/classes/ethermancer.c#L207) (#679).
- [Frost Bolt](../../src/classes/ethermancer.c#L1340) (#455).
- [Frostbite](../../src/magic/magic.c#L1064) (#325).
- [Full Harm](../../src/magic/magic.c#L6141) (#243).
- [Gaseous Cloud](../../src/magic/smagic.c#L1645) (#366).
- [Ghastly Touch](../../src/magic/magic.c#L19304) (#572).
- [Glass Bomb](../../src/classes/salchemist.c#L2468) (#491).
- [Grease](../../src/classes/salchemist.c#L2582) (#493).
- [Greater Earthen Grasp](../../src/magic/smagic.c#L2206) (#246).
- [Greater Living Stone](../../src/magic/magic.c#L3452) (#425).
- [Greater Pythonsting](../../src/magic/smagic.c#L2324) (#222).
- [Greater Soul Disturbance](../../src/magic/smagic.c#L1452) (#219).
- [Greater Spirit Anguish](../../src/magic/smagic.c#L1515) (#381).
- [Hammer](../../src/classes/sillusionist.c#L1726) (#413).
- [Harm](../../src/magic/magic.c#L6085) (#27).
- [Harmonic Resonance](../../src/magic/magic.c#L6428) (#361).
- [Holy Word](../../src/magic/magic.c#L19946) (#123).
- [Horrid Wilting](../../src/magic/blispells.c#L901) (#632).
- [Hurricane](../../src/magic/spells.c#L3216) (#449).
- [Ice Missile](../../src/magic/smagic.c#L871) (#191).
- [Ice Spikes](../../src/classes/ethermancer.c#L4892) (#648).
- [Ice Storm](../../src/magic/magic.c#L18727) (#111).
- [Immolate](../../src/magic/magic.c#L23976) (#277).
- [Implosion](../../src/magic/blispells.c#L1106) (#634).
- [Imprisonment](../../src/classes/sillusionist.c#L2290) (#419).
- [Incendiary Cloud](../../src/magic/magic.c#L18063) (#110).
- [Induce Tupor](../../src/classes/ethermancer.c#L2047) (#463).
- [Inflict Pain](../../src/classes/psionics.c#L2847) (#181).
- [Insects](../../src/classes/sillusionist.c#L362) (#402).
- [Invoke Negative Energy](../../src/magic/magic.c#L1355) (#320).
- [Judgement](../../src/magic/magic.c#L23801) (#265).
- [Life Bolt](../../src/magic/magic.c#L28641) (#586).
- [Life Leech](../../src/magic/magic.c#L1776) (#618).
- [Lightning Bolt](../../src/magic/magic.c#L1214) (#30).
- [Lightning Ring](../../src/magic/magic.c#L4894) (#374).
- [Living Stone](../../src/magic/magic.c#L3320) (#398).
- [Magic Missile](../../src/magic/magic.c#L884) (#32).
- [Magma Burst](../../src/magic/magic.c#L24275) (#394).
- [Major Paralysis](../../src/magic/magic.c#L10689) (#101).
- [Malison](../../src/magic/smagic.c#L4011) (#212).
- [Memory Block](../../src/classes/psionics.c#L2076) (#344).
- [Mental Anguish](../../src/classes/psionics.c#L2021) (#342).
- [Meteorswarm](../../src/magic/magic.c#L5109) (#59).
- [Minor Paralysis](../../src/magic/magic.c#L10771) (#100).
- [Molecular Agitation](../../src/classes/psionics.c#L371) (#156).
- [Molevision](../../src/magic/smagic.c#L2972) (#199).
- [Molten Spray](../../src/magic/smagic.c#L1319) (#235).
- [Mousestrength](../../src/magic/smagic.c#L3121) (#202).
- [Napalm](../../src/classes/salchemist.c#L2399) (#375).
- [Natures Calling](../../src/magic/magic.c#L27219) (#539).
- [Negative Concussion Blast](../../src/magic/magic.c#L26199) (#378).
- [Nether Touch](../../src/magic/magic.c#L9198) (#326).
- [Nightmare](../../src/classes/sillusionist.c#L1416) (#410).
- [Nitrogen](../../src/classes/salchemist.c#L2503) (#494).
- [Nivards Wicked Firebrand](../../src/magic/smagic.c#L5900) (#555).
- [Nova](../../src/magic/magic.c#L6416) (#359).
- [Obtenebration](../../src/magic/magic.c#L17955) (#613).
- [Plague](../../src/magic/magic.c#L13982) (#439).
- [Pleasantry](../../src/magic/magic.c#L25574) (#296).
- [Poison](../../src/magic/magic.c#L10620) (#33).
- [Polar Vortex](../../src/classes/ethermancer.c#L3452) (#550).
- [Power Word Blind](../../src/magic/magic.c#L20447) (#120).
- [Power Word Kill](../../src/magic/magic.c#L19037) (#119).
- [Power Word Stun](../../src/magic/magic.c#L20494) (#121).
- [Prismatic Ray](../../src/magic/magic.c#L642) (#364).
- [Prismatic Spray](../../src/magic/magic.c#L727) (#107).
- [Psionic Cloud](../../src/classes/psionics.c#L2124) (#345).
- [Psionic Wave Blast](../../src/classes/psionics.c#L3622) (#582).
- [Psychic Crush](../../src/classes/psionics.c#L1469) (#308).
- [Purge](../../src/classes/ethermancer.c#L1951) (#323).
- [Purge Living](../../src/magic/magic.c#L18532) (#461).
- [Pyrokinesis](../../src/classes/psionics.c#L3254) (#612).
- [Pythonsting](../../src/magic/smagic.c#L2264) (#197).
- [Ray Of Enfeeblement](../../src/magic/magic.c#L8819) (#71).
- [Razor Wind](../../src/classes/ethermancer.c#L4003) (#589).
- [Recharger](../../src/magic/magic.c#L12609) (#55).
- [Restore Spirit](../../src/magic/magic.c#L1431) (#604).
- [Reveal True Form](../../src/magic/smagic.c#L5308) (#224).
- [Sandstorm](../../src/magic/blispells.c#L1290) (#636).
- [Scalding Blast](../../src/magic/smagic.c#L1218) (#196).
- [Scathing Wind](../../src/magic/smagic.c#L1828) (#223).
- [Scorching Touch](../../src/magic/smagic.c#L1276) (#205).
- [Shadow Monster](../../src/classes/sillusionist.c#L230) (#401).
- [Shadow Spawn](../../src/classes/sillusionist.c#L3276) (#535).
- [Shatter](../../src/magic/magic.c#L18316) (#487).
- [Shocking Grasp](../../src/magic/magic.c#L1167) (#37).
- [Shrewtameness](../../src/magic/smagic.c#L3590) (#210).
- [Silence](../../src/magic/magic.c#L20143) (#127).
- [Sirens Song](../../src/magic/magic.c#L6505) (#360).
- [Slashing Darkness](../../src/classes/necromancy.c#L3460) (#561).
- [Sleep](../../src/magic/magic.c#L11470) (#38).
- [Slowness](../../src/magic/magic.c#L10824) (#102).
- [Snailspeed](../../src/magic/smagic.c#L2746) (#198).
- [Solar Flare](../../src/magic/magic.c#L20041) (#431).
- [Solbeeps Missile Barrage](../../src/magic/magic.c#L4650) (#549).
- [Soul Disturbance](../../src/magic/smagic.c#L1402) (#207).
- [Spike Growth](../../src/magic/spells.c#L3088) (#507).
- [Spinal Corruption](../../src/classes/psionics.c#L1906) (#343).
- [Spirit Anguish](../../src/magic/smagic.c#L1592) (#216).
- [Spore Burst](../../src/magic/magic.c#L28148) (#505).
- [Spore Cloud](../../src/magic/magic.c#L28262) (#504).
- [Squall](../../src/classes/ethermancer.c#L2465) (#465).
- [Static Discharge](../../src/classes/ethermancer.c#L3851) (#563).
- [Sticks To Snakes](../../src/magic/magic.c#L10273) (#370).
- [Stornogs Metamagic Shroud](../../src/magic/magic.c#L10895) (#309).
- [Strong Acid](../../src/classes/salchemist.c#L2433) (#376).
- [Stunning Visions](../../src/classes/sillusionist.c#L769) (#406).
- [Summon Ghasts](../../src/magic/magic.c#L19543) (#571).
- [Sunray](../../src/magic/magic.c#L20086) (#124).
- [Supernova](../../src/classes/ethermancer.c#L2934) (#529).
- [Taint](../../src/classes/necromancy.c#L3740) (#596).
- [Titan](../../src/classes/sillusionist.c#L2624) (#421).
- [Tormenting Spirits](../../src/magic/smagic.c#L6279) (#580).
- [Toxic Fog](../../src/magic/blispells.c#L1641) (#640).
- [Turn Undead](../../src/magic/magic.c#L17525) (#128).
- [Undeath To Death](../../src/classes/necromancy.c#L3619) (#576).
- [Unholy Wind](../../src/magic/magic.c#L18486) (#317).
- [Unholy Word](../../src/magic/magic.c#L19747) (#122).
- [Voice Of Creation](../../src/magic/magic.c#L19904) (#611).
- [Vortex Of Fear](../../src/classes/paladins.c#L329) (#329).
- [Waves Of Fatigue](../../src/magic/blispells.c#L634) (#630).
- [Wither](../../src/magic/magic.c#L2236) (#103).
- [Word Of Command](../../src/magic/magic.c#L25761) (#306).

### Room, terrain, and exit effects (37)

- [Airy Water](../../src/magic/magic.c#L15622) (#274).
- [Binding Wind](../../src/magic/magic.c#L8627) (#498).
- [Consecrate Land](../../src/magic/magic.c#L8474) (#358).
- [Control Weather](../../src/magic/spells.c#L111) (#11).
- [Create Sound](../../src/classes/psionics.c#L1376) (#165).
- [Depressed Earth](../../src/magic/spells.c#L2448) (#518).
- [Desecrate Land](../../src/magic/blispells.c#L266) (#627).
- [Earthen Tomb](../../src/magic/spells.c#L1685) (#399).
- [Ethereal Grounds](../../src/magic/spells.c#L1890) (#426).
- [Forbiddance](../../src/magic/blispells.c#L544) (#629).
- [Grow](../../src/magic/spells.c#L2530) (#444).
- [Illusionary Wall](../../src/classes/sillusionist.c#L1378) (#403).
- [Life Ward](../../src/magic/spells.c#L1259) (#335).
- [Lightning Curtain](../../src/magic/spells.c#L1427) (#154).
- [Prismatic Cube](../../src/magic/spells.c#L1515) (#264).
- [Stornogs Shimmering Starshell](../../src/magic/magic.c#L24702) (#282).
- [Summon Insects](../../src/magic/magic.c#L8572) (#501).
- [Tempest Terrain](../../src/classes/ethermancer.c#L2162) (#475).
- [Transmute Air To Water](../../src/magic/spells.c#L2261) (#514).
- [Transmute Lava To Rock](../../src/magic/spells.c#L2388) (#519).
- [Transmute Mud To Rock](../../src/magic/spells.c#L1946) (#509).
- [Transmute Mud To Water](../../src/magic/spells.c#L2078) (#511).
- [Transmute Rock To Lava](../../src/magic/spells.c#L2320) (#516).
- [Transmute Rock To Mud](../../src/magic/spells.c#L2007) (#510).
- [Transmute Water To Air](../../src/magic/spells.c#L2200) (#513).
- [Transmute Water To Mud](../../src/magic/spells.c#L2136) (#512).
- [Wall Of Air](../../src/classes/ethermancer.c#L5009) (#649).
- [Wall Of Bones](../../src/classes/necromancy.c#L3870) (#153).
- [Wall Of Flames](../../src/magic/spells.c#L1152) (#148).
- [Wall Of Force](../../src/magic/spells.c#L1374) (#152).
- [Wall Of Ice](../../src/magic/spells.c#L1210) (#149).
- [Wall Of Iron](../../src/magic/spells.c#L1334) (#151).
- [Wall Of Stone](../../src/magic/spells.c#L1295) (#150).
- [Wandering Woods](../../src/magic/magic.c#L8438) (#349).
- [Watching Wall](../../src/classes/sillusionist.c#L1321) (#409).
- [Web](../../src/magic/spells.c#L1466) (#295).
- [Wind Tunnel](../../src/magic/magic.c#L8671) (#499).

### Other targeted or encounter actions (9)

- [Aura Of Rebirth](../../src/magic/spells.c#L919) (#373).
- [Channel](../../src/magic/spells.c#L294) (#313).
- [Clairvoyance](../../src/magic/magic.c#L7141) (#69).
- [Excogitate](../../src/classes/psionics.c#L4875) (#574).
- [Lend Health](../../src/classes/psionics.c#L2959) (#183).
- [Reveal Spirit Essence](../../src/magic/smagic.c#L5446) (#250).
- [Tranquility](../../src/magic/magic.c#L22613) (#353).
- [Transfer Wellness](../../src/magic/smagic.c#L2500) (#194).
- [Wizard Eye](../../src/magic/magic.c#L7105) (#68).

### Travel and anchors (34)

- [Blink](../../src/magic/magic.c#L26623) (#433).
- [Bloodstone](../../src/magic/blispells.c#L1872) (#643).
- [Corpse Portal](../../src/magic/magic.c#L28873) (#623).
- [Depart](../../src/classes/psionics.c#L3456) (#583).
- [Dimension Door](../../src/magic/magic.c#L7259) (#63).
- [Dream Travel](../../src/classes/sillusionist.c#L1875) (#415).
- [Ether Warp](../../src/classes/psionics.c#L4386) (#281).
- [Ethereal Rift](../../src/classes/psionics.c#L4264) (#346).
- [Ethereal Travel](../../src/classes/ethermancer.c#L3498) (#551).
- [Etheric Gust](../../src/classes/ethermancer.c#L4500) (#594).
- [Etherportal](../../src/magic/smagic.c#L5978) (#242).
- [Frost Beacon](../../src/classes/ethermancer.c#L1087) (#468).
- [Gate](../../src/magic/spells.c#L437) (#87).
- [Gate To Ardgral](../../src/classes/sillusionist.c#L3082) (#536).
- [Group Recall](../../src/magic/magic.c#L11849) (#245).
- [Group Teleport](../../src/magic/magic.c#L7495) (#488).
- [Mind Travel](../../src/classes/psionics.c#L794) (#379).
- [Moonstone](../../src/magic/magic.c#L27758) (#305).
- [Moonwell](../../src/magic/magic.c#L27648) (#142).
- [Nether Gate](../../src/magic/spells.c#L576) (#332).
- [Plane Shift](../../src/magic/spells.c#L733) (#86).
- [Radial Navigation](../../src/classes/psionics.c#L4143) (#303).
- [Relocate](../../src/magic/magic.c#L7460) (#80).
- [Shadow Gate](../../src/magic/magic.c#L27555) (#334).
- [Shadow Travel](../../src/classes/sillusionist.c#L571) (#405).
- [Spirit Jump](../../src/magic/smagic.c#L5593) (#251).
- [Spirit Walk](../../src/magic/smagic.c#L523) (#482).
- [Summon](../../src/magic/magic.c#L11955) (#40).
- [Teleport](../../src/magic/magic.c#L7634) (#2).
- [Thought Beacon](../../src/classes/psionics.c#L4543) (#537).
- [Way Of The Wind](../../src/magic/magic.c#L7460) (#462).
- [Windwalk](../../src/classes/ethermancer.c#L942) (#453).
- [Word Of Recall](../../src/magic/magic.c#L11696) (#42).
- [Wormhole](../../src/classes/psionics.c#L4686) (#241).

### Corpse and object-dependent pet/resurrection operations (27)

- [Animate Dead](../../src/classes/necromancy.c#L1147) (#82).
- [Call Archon](../../src/classes/necromancy.c#L1181) (#616).
- [Call Asura](../../src/classes/necromancy.c#L1154) (#599).
- [Call Avatar](../../src/classes/necromancy.c#L2385) (#598).
- [Call Bralani](../../src/classes/necromancy.c#L1159) (#600).
- [Call Deva](../../src/classes/necromancy.c#L1165) (#603).
- [Call Knight](../../src/classes/necromancy.c#L1170) (#601).
- [Call Liberator](../../src/classes/necromancy.c#L1175) (#602).
- [Call Titan](../../src/classes/necromancy.c#L1476) (#597).
- [Compact Corpse](../../src/classes/necromancy.c#L4021) (#650).
- [Create Dracolich](../../src/classes/necromancy.c#L1741) (#143).
- [Create Golem](../../src/classes/necromancy.c#L2126) (#485).
- [Create Greater Dracolich](../../src/classes/necromancy.c#L2678) (#380).
- [Embalm](../../src/magic/magic.c#L22174) (#145).
- [Hand Of Death](../../src/magic/magic.c#L20976) (#341).
- [Lesser Resurrect](../../src/magic/magic.c#L21413) (#490).
- [Mass Embalm](../../src/magic/magic.c#L22137) (#338).
- [Mass Preserve](../../src/magic/magic.c#L22147) (#339).
- [Preserve](../../src/magic/magic.c#L21344) (#94).
- [Raise Lich](../../src/classes/necromancy.c#L1142) (#271).
- [Raise Shadow](../../src/classes/necromancy.c#L1130) (#486).
- [Raise Spectre](../../src/classes/necromancy.c#L1118) (#268).
- [Raise Vampire](../../src/classes/necromancy.c#L1136) (#270).
- [Raise Wraith](../../src/classes/necromancy.c#L1124) (#269).
- [Resurrect](../../src/magic/magic.c#L20976) (#88).
- [Return Soul](../../src/magic/magic.c#L9435) (#644).
- [Unmaking](../../src/magic/magic.c#L9435) (#319).

### Unimplemented, disabled, or placeholder (7)

- [Auctions Disabled](../../src/classes/skills.c#L592) (#621).
- [Battle Mages Aura](../../src/classes/skills.c#L595) (#622).
- [Corpseform](../../src/classes/necromancy.c#L3221) (#377).
- [Dark Compact](../../src/magic/magic.c#L7371) (#340).
- [Greater Flicker](../../src/classes/sillusionist.c#L2852) (#430).
- [Ritus Draconum](../../src/magic/magic.c#L30036) (#667).
- [Summon Spirit](../../src/magic/smagic.c#L4894) (#218).

### Permanent or special progression changes (13)

- [Age](../../src/magic/magic.c#L8943) (#75).
- [Curse Of Yzar](../../src/magic/spells.c#L3879) (#647).
- [Iagi](../../src/magic/magic.c#L27389) (#541).
- [Icha](../../src/magic/magic.c#L27512) (#548).
- [Icon](../../src/magic/magic.c#L27425) (#543).
- [Idex](../../src/magic/magic.c#L27407) (#542).
- [Iint](../../src/magic/magic.c#L27478) (#546).
- [Iluck](../../src/magic/magic.c#L27443) (#544).
- [Ipow](../../src/magic/magic.c#L27460) (#545).
- [Istr](../../src/magic/magic.c#L27371) (#540).
- [Iwis](../../src/magic/magic.c#L27495) (#547).
- [Rejuvenate Major](../../src/magic/magic.c#L8980) (#70).
- [Rested](../../src/magic/spells.c#L3911) (#651).

</details>

## Verification and use of this inventory

The count was extracted from the active, uncommented set initializer and
joined to zone headers named by `areas/AREA`. All 353 registered zone headers
were read, including infrastructure and special records; this is not a claim
that all 353 are playable set destinations. Effect names and spell functions
were joined to the active registrations in
[`skills.c`](../../src/classes/skills.c) and
[`epic_skills.c`](../../src/classes/epic_skills.c). Candidate notes were checked
against their implementations; effect-ID aliases were not silently deduplicated.

Checks: unique zone/effect pairs; no unresolved effect names; used counts sum
to 206; adding the stale rows gives 209; every candidate has count zero in
both counts; all candidate implementation links resolve. This was a source
and document check. No server operations, C/C++ changes, build, or gameplay
qualification were needed or performed.

Before assigning a retained candidate, choose its piece threshold and power,
then test equip/unequip, mixed sets, an ordinary cast of the same effect, and
save/reload. Preserve existing restrictions and stat/speed caps. Keep new set
definitions independent of roaming-mob spawn choices, as required by #706.
