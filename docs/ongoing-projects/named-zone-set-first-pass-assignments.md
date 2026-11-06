# Named zone sets: complete assignment plan and remaining work

Status: 183 reviewed additions (104 original + 79 wider) installed in the implementation catalog; final gameplay/storage/publication gates pending.
Date: 2026-11-06.
Inspected `master`: `2d2a7d48dea91dbe773701790239db76f59806c2`.

Implementation entry point: [end-to-end plan](named-zone-set-implementation-plan.md),
including the seven-zone fixes, legacy-item policy, and verification gates.

## Initial two-pass scope and counts

The initial pass used each of the **42 retained candidates** in the
[effect inventory](named-zone-set-effect-inventory.md#unused-effects-that-could-become-set-bonuses)
once. This reuse pass adds **62 more assignments**, giving every zone in
[issue #706's 104-zone roster](https://github.com/LuminariMUD/Duris/issues/706)
one proposed effect. The issue body was rechecked; its roster was last updated
on 2026-11-05 at 08:15:32 UTC. Zone numbers remain the identity keys.

| Planning measure | Zones |
|---|---:|
| Missing-set zones in the issue's current roster | 104 |
| Initial assignments | 42 |
| Additional assignments in the reuse pass | 62 |
| Initial two-pass zones with a proposed effect | 104 |
| Zones still needing an effect choice | 0 |
| Assigned zones with known title/naming prerequisites | 7 |

**These are proposed assignments.** All 104 original roster zones now have set-table
rows in the implementation catalog, together with 79 wider-review additions. Seven needed the identity/title repairs now in
the PR stack; their remaining gameplay gates are listed below. The complete
plan covers this roster; the issue's wider world
review can still identify other eligible areas.

## Assignment and reuse rules

- Give each zone one proposed effect. The original 42 pairings are preserved;
  every one of those effects gains at least one additional home in this pass.
- Count a home as a distinct zone ID: currently configured loaded zones plus
  proposed assignments. Exclude stale IDs #30 and #250. These are definition
  and planning counts, separate from drop frequency or live player usage.
- Prefer effects with **one home at the start of the reuse pass**, while keeping
  the theme convincing. Of 62 new assignments, **60 use a one-home effect**.
  These spread 48 distinct one-home effects; some get a third home where the
  same setting or creature theme repeats. The remaining two choices are Cold
  Protection for Northern Lakes and Water Breathing for the Seacaves.
- The existing-set additions are limited to eight simple effects: Agility,
  Enhance Agility, Enhance Strength, Farsee, Protection from Cold, Protection
  from Fire, Protection from Lightning, and Water Breathing. Rarity does not
  override the earlier high-impact or extra-handling exclusions.
- Each of the 42 initially unused candidates ends with **two or three planned
  homes**. The reuse pool's final combined counts are 36 effects with two homes,
  13 with three, and Water Breathing with five. The full counts appear below.
- Thematic explanations are design judgments drawn from authored settings,
  rooms, and inhabitants. Existing restrictions still apply: Guardian Spirits
  remains **Shaman-only**, Virtue retains its native alignment condition, and light/darkness
  effects retain their exclusions.
- Piece requirements are recorded for every assignment below. Preserve the
  ordinary matching-piece HP bonus and existing spell caps.

## Balance qualification and final piece requirements

The original 104 zone/effect pairings and all effect-home counts are retained.
**98 additions unlock at three pieces, four at five pieces, and two at six
pieces.** This is a conservative initial choice, not live-player usage evidence.
The native functions are unchanged:

- Adrenaline Control (#157, both assignments) needs **five** pieces because its
  fixed +15 Strength and +15 Constitution exceeds the single-stat grants in
  the default tier. More pieces do not increase those two modifiers.
- Battletide (#395, both assignments) needs **five** pieces because its fixed
  +10 hitroll and +10 damroll exceeds Combat Mind/Lifelust at the default tier.
- Guardian Spirits (#579, #422 and #780) needs **six** pieces. Its fixed 150–200
  AC protection is much larger than the other proposed armor grants and does
  not shrink with a lower invocation level. It still requires a **Shaman
  wearer**, with any specialization; non-Shamans receive no substitute bonus.
- All other assignments need **three** pieces. Each receives one native effect
  tier; the existing HP formula is separate (+5 HP at three pieces, +15 at five,
  +20 at six). Existing catalog rows retain their original thresholds.

The following are raw native affect modifiers at invocation levels 30, 50 and
56 (three, five and six pieces). Ordinary character stat caps still apply.
Counts above six retain the same capped invocation level. Native class-specific
adjustments inside a handler remain in force, including the Animalist cases below.

| Native effect | Three pieces | Five pieces | Six or more pieces |
|---|---|---|---|
| Adrenaline Control | +15 STR / +15 CON | +15 / +15 | +15 / +15 |
| Battletide | +10 hit / +10 damage | +10 / +10 | +10 / +10 |
| Combat Mind | +5 hit / +3 damage | +8 / +6 | +9 / +7 |
| Dexterity; Agility | +10 respective stat | +10 | +10 |
| Divine Fury | +6 hit / +6 damage | +10 / +10 | +11 / +11 |
| Enhance STR, DEX or AGI | +8 respective stat | +13 | +15 |
| Enhance Constitution | +7 CON | +11 | +12 |
| Fortitude | +1–5 CON by wearer level | Same | Same |
| Lifelust | +3 hit / +3 damage | +4 / +4 | +4 / +4 |
| Pulchritude | +20 CHA | +30 | +30 |
| Serendipity | +12 luck | +18 | +18 |
| Vapor Strike | +3–11 hit | Same | Same |
| Warring Zeal | +6 hit | +10 | +11 |
| Wolfspeed, non-Animalist | +17–19 vitality | +27–29 | +30–32 |
| Displacement | −60 AC | −100 | −112 |
| Energy Containment | −3 spell save | −6 | −7 |
| Enhance Armor; Phantom Armor | −30 AC | −50 | −56 |
| Vapor Armor | −37 AC | −62 | −70 |
| Guardian Spirits, Shaman | −150 to −200 AC | Same | Same |
| Virtue | Native conditional 10% accuracy bonus | Same | Same |

Three/five-piece columns for the higher-requirement assignments are qualification
samples, not reachable unlocks. Utility/protection effects retain their native
flags and exclusion rules; their durations are frozen alongside the modifiers in
the [executable qualification](../../tests/async/test_named_set_effect_ownership.py).
Fortitude depends on the wearer's level rather than the invocation level. Detect
Good/Evil keep `KludgeDuration` (a level-12 wearer gets one tick at these sample
invocation levels); Lodestone lasts 5–7 ticks regardless of pieces. Divine Fury
and Warring Zeal retain their two-tick durations and native flags.

Animalist Wolfspeed adds a native wearer-level-dependent roll after the shared
invocation cap. At wearer level 56 it grants +22–33 / +32–43 / +35–46 vitality
at the three sample piece counts. Animalist Hawkvision adds 20 invocation levels
for its duration. Shaman Sense Spirit lasts longer than non-Shaman Sense Spirit.
These native class rules are preserved and exercised at wearer levels 12 and 56.

Virtue works for **good wearers against non-good targets** and **evil wearers
against non-evil targets**, including neutral targets. A neutral wearer gets no
accuracy bonus. The test executes the real combat condition across both alignment
boundaries; it is more precise than the earlier “opposed alignment” wording.
Holy Light and Mage Flame share a light bit; neither can coexist with Globe of
Darkness. Phantom/Vapor Armor retain the shared armor exclusion; Enhance Armor
retains its native ability to stack with armor. Hawkvision excludes Molevision,
Wolfspeed excludes other Shaman movement spells, and Infravision respects existing
infravision and Ophidian Eyes.

**Evidence:** all 50 effects are checked against their actual registrations and
real spell/helper bodies at 3/5/6/12/40 pieces, both RNG endpoints, wearer levels
12/56, and non-Shaman/Shaman/Animalist classes. The regression checks native
modifiers, durations, bitvectors, provenance, repeat grants, ordinary casts in both
orders, cleanup, expiry and dispel flags. Light exclusion/recalculation calls and
Virtue's actual combat branch are covered. Character stat totals, room-light
totals, output and command dispatch remain fixture boundaries; the complete
gameplay/storage gates in the main plan still apply. No expansion row is installed
by this qualification chunk.

## The 42 proposed assignments

Sorted by zone number. Zone links point to the active zone definitions; effect
links point to the spell implementations used by the candidate inventory.

| Zone ID | Zone | Assigned effect (game ID) | Pieces | Theme and existing restrictions |
|---:|---|---|---:|---|
| 49 | [The Halfling Silver Mine](../../areas/zon/mining.zon) | [Lodestone Vision](../../src/magic/magic.c#L12484) (#617) | 3 | Mineral detection directly matches the silver mine and its miners. |
| 50 | [Labyrinth of No Return](../../areas/zon/labyrinth.zon) | [Detect Illusion](../../src/classes/sillusionist.c#L1797) (#414) | 3 | Seeing through deception fits a labyrinth and its confusing passages. |
| 69 | [The Caverns of the Worms](../../areas/zon/worms.zon) | [Slow Poison](../../src/magic/magic.c#L17814) (#130) | 3 | A poison-control utility theme fits underground worms and crawling vermin; the effect slows poison rather than removing it. |
| 108 | [The Haunted Woods](../../areas/zon/hwood.zon) | [Phantom Armor](../../src/classes/sillusionist.c#L131) (#400) | 3 | Phantom protection matches the haunted woodland theme. |
| 137 | [Tundra](../../areas/zon/tundra.zon) | [Fortitude](../../src/magic/magic.c#L6345) (#348) | 3 | Constitution fits the endurance demanded by the icy tundra. |
| 148 | [Bandit Camp](../../areas/zon/banditca.zon) | [Dexterity](../../src/magic/magic.c#L11563) (#73) | 3 | Nimble hands and footwork fit the bandit camp. |
| 164 | [Lord Krimeneha's Mansion](../../areas/zon/krimman.zon) | [Pulchritude](../../src/magic/magic.c#L8075) (#347) | 3 | A charm/appearance bonus suits a noble mansion and its alluring, sinister inhabitants. |
| 234 | [Mosswood](../../areas/zon/moss.zon) | [Protection From Gas](../../src/magic/magic.c#L21917) (#104) | 3 | Gas protection fits the area's mold and fungus creatures. |
| 326 | [The Fortress of Dreams](../../areas/zon/eth2.zon) | [Displacement](../../src/classes/psionics.c#L2206) (#169) | 3 | A shifting defensive image suits the fortress's ethereal and dreamlike setting. |
| 355 | [The Underground Lava Caves](../../areas/zon/lavcav.zon) | [Infravision](../../src/magic/magic.c#L22089) (#106) | 3 | Heat-oriented vision fits dark lava caves and their fire creatures. |
| 364 | [Arachdrathos - Drow City](../../areas/zon/arac-web.zon) | [Globe Of Darkness](../../src/magic/magic.c#L17667) (#302) | 3 | A carried darkness sphere suits an underground Drow city. Existing light/darkness exclusions apply. |
| 407 | [Home of the Divine](../../areas/zon/divhome.zon) | [Sense Holiness](../../src/magic/magic.c#L7067) (#316) | 3 | Sensing holiness directly matches the angels and divine guardians. |
| 444 | [Githzerai Stronghold](../../areas/zon/githzer.zon) | [Combat Mind](../../src/classes/psionics.c#L1094) (#163) | 3 | Mental discipline suits a Githzerai stronghold and its trained defenders. |
| 455 | [Celestial Plane](../../areas/zon/celestia.zon) | [Protection From Evil](../../src/magic/magic.c#L10975) (#34) | 3 | Protection from evil suits Celestia's guardians and celestial war grounds. |
| 490 | [The Desert City of Venan'Trut](../../areas/zon/desert.zon) | [Sense Follower](../../src/magic/magic.c#L24629) (#279) | 3 | Finding followers fits a busy desert city of travelers, merchants, and pack animals. |
| 575 | [the Mountain of Peril Peaks](../../areas/zon/nexus.zon) | [Adrenaline Control](../../src/classes/psionics.c#L412) (#157) | 5 | The dangerous mountain trails reward physical readiness: a Strength/Constitution theme. |
| 590 | [The Ravenloft Catacombs](../../areas/zon/ravenloft2.zon) | [Sense Life](../../src/magic/magic.c#L12385) (#44) | 3 | Sensing living creatures is useful thematic contrast in undead-filled catacombs. |
| 664 | [The Battlefield](../../areas/zon/battlefi.zon) | [Warring Zeal](../../src/magic/magic.c#L25432) (#680) | 3 | Battle focus and accuracy fit the soldiers and contested ground. |
| 708 | [Enclave of the Opal Phoenix](../../areas/zon/opalphoenix.zon) | [Holy Light](../../src/magic/magic.c#L17597) (#615) | 3 | A holy light theme matches the enclave's phoenix identity. Existing light/darkness exclusions apply. |
| 709 | [The Hall of Knighthood](../../areas/zon/knight.zon) | [Virtue](../../src/magic/magic.c#L6927) (#515) | 3 | Chivalric virtue fits the knights and their opposed vices. Good/non-good and evil/non-evil combat conditions apply, including neutral targets. |
| 740 | [Bloodstone Keep](../../areas/zon/bs.zon) | [Battletide](../../src/magic/magic.c#L16594) (#395) | 5 | A martial bonus for Bloodstone's fortified keep and its guards. |
| 760 | [The Sky City of Ultarium](../../areas/zon/cosmic.zon) | [Hawkvision](../../src/magic/smagic.c#L3281) (#204) | 3 | Long sight fits a high mountain sky city and its starwatcher setting. |
| 766 | [The Jade Empire](../../areas/zon/jade.zon) | [Enhance Dexterity](../../src/classes/psionics.c#L2564) (#176) | 3 | Controlled, precise movement suits the Jade Empire's martial tradition. |
| 780 | [Tribal Oasis](../../areas/zon/oasis.zon) | [Guardian Spirits](../../src/magic/smagic.c#L208) (#579) | 6 | Ancestral protection fits a tribal settlement with a mantis shaman. **Shaman wearers only**, as required by the existing spell. |
| 805 | [The Temple to Skrentherlog](../../areas/zon/yuan_ti.zon) | [Divine Fury](../../src/magic/magic.c#L22267) (#310) | 3 | Religious battle fury suits the Yuan-ti temple and its warriors. |
| 823 | [The Swamp Laboratory of Khul'Lor](../../areas/zon/lab.zon) | [Protection From Acid](../../src/magic/magic.c#L21936) (#105) | 3 | Acid protection is a fitting chemical-defense theme for a slimy swamp laboratory. |
| 831 | [Alatorin - the Forge City](../../areas/zon/alatorin.zon) | [Enhance Armor](../../src/classes/psionics.c#L2459) (#174) | 3 | Stronger armor suits a forge city and its metalworking identity. |
| 875 | [The 222nd Layer of the Abyss](../../areas/zon/juiblex.zon) | [Protection From Good](../../src/magic/magic.c#L11004) (#81) | 3 | Protection from good suits a demon- and slime-filled layer of the Abyss. |
| 877 | [Valley of the Snow Ogres](../../areas/zon/snogres.zon) | [Enhance Constitution](../../src/classes/psionics.c#L2650) (#178) | 3 | Hardiness fits the snow-ogre tribes and their cold mountain valley. |
| 878 | [The Church of the Eternal Dusk](../../areas/zon/church.zon) | [Detect Good](../../src/magic/magic.c#L9283) (#91) | 3 | An alignment sense gives the church a religious utility theme. |
| 890 | [The Village of New Hope](../../areas/zon/newhope.zon) | [Serendipity](../../src/magic/magic.c#L8284) (#352) | 3 | A small luck theme matches the settlement's promise of new hope. |
| 910 | [The Realm of Barovia](../../areas/zon/barovia.zon) | [Lifelust](../../src/magic/magic.c#L7776) (#321) | 3 | A life-hungry combat blessing fits Barovia's undead-haunted setting. |
| 933 | [Centaur Villages](../../areas/zon/centaur_zone.zon) | [Wolfspeed](../../src/magic/smagic.c#L2683) (#193) | 3 | A larger movement pool suits centaur travelers and the area's wolves. |
| 943 | [The Behemoth Herders](../../areas/zon/herders.zon) | [Scent Of The Bloodhound](../../src/magic/smagic.c#L2353) (#517) | 3 | Tracking by scent fits an area centered on herders, riders, and behemoths. |
| 989 | [Ruined Temple of Tezcatlipoca](../../areas/zon/tezcat.zon) | [Detect Evil](../../src/magic/magic.c#L9246) (#90) | 3 | Sensing evil suits the exploration of a ruined dark temple. |
| 1310 | [The BrimStone Forge](../../areas/zon/brimeforge.zon) | [Mage Flame](../../src/magic/magic.c#L17626) (#297) | 3 | A small magical flame fits the BrimStone Forge's fire-and-smithing identity. Existing light/darkness exclusions apply. |
| 1382 | [Mitashi - Capital City of the Jade Empire](../../areas/zon/mitashi.zon) | [Comprehend Languages](../../src/magic/magic.c#L17843) (#132) | 3 | Language comprehension fits an imperial capital populated by multiple clans, merchants, and visitors. |
| 1385 | [The Savannah of Broken Trusts](../../areas/zon/savannah.zon) | [Protection From Animals](../../src/magic/magic.c#L21864) (#383) | 3 | Protection from wild beasts fits the savannah's leopards, panthers, and other animals. |
| 1398 | [The Para-Elemental Plane of Smoke](../../areas/zon/smoke.zon) | [Vapor Strike](../../src/classes/ethermancer.c#L1134) (#467) | 3 | A vapor-themed accuracy bonus fits a plane populated by smoke creatures. |
| 1424 | [The Royal Mausoleum of Castle IceCrag](../../areas/zon/Voluntown.zon) | [Sense Spirit](../../src/magic/smagic.c#L4244) (#211) | 3 | Spirit detection matches a royal mausoleum and its dead inhabitants. |
| 3000 | [The Chasm of the Misty Vale](../../areas/zon/thechasmofthemistyvale.zon) | [Vapor Armor](../../src/classes/ethermancer.c#L104) (#452) | 3 | Mist-shaped armor fits the Misty Vale and its forested chasm approach. |
| 4020 | [The Arcaneum of L'srillizzin](../../areas/zon/library.zon) | [Energy Containment](../../src/classes/psionics.c#L2405) (#173) | 3 | Containing magical energy suits the Arcaneum and its elemental golems. |

## The 62 additional assignments

The home-count column is the combined configured-plus-initial-plan count at
the **start** of this reuse pass. It is not a running count after each row.
Zone links identify the area; effect links follow the source inventory.

| Zone ID | Zone | Reused effect (game ID) | Pieces | Homes before reuse pass | Theme and existing restrictions |
|---:|---|---|---:|---:|---|
| 13 | [Braddistock Mansion](../../areas/zon/braddistock.zon) | [Phantom Armor](../../src/classes/sillusionist.c#L131) (#400) | 3 | 1 | The mansion's resident spirit and ratman mages fit a phantom-defense theme. Explicit origin IDs now separate the two Braddistock zones; ambiguous legacy tags stay HP-only. |
| 17 | [The Docks of Quietus Quay](../../areas/zon/quietus.zon) | [Dexterity](../../src/magic/magic.c#L11563) (#73) | 3 | 1 | Sure hands and footing fit work around the docks, warehouses, and steep harbor approaches. |
| 22 | [The Seacaves](../../areas/zon/seacaves.zon) | [Water Breathing](../../src/classes/skills.c#L1571) (#85) | 3 | 4 | Water breathing directly matches the sea caves, coastal pools, and water elementals. This stronger thematic fit takes priority over its existing four homes. |
| 42 | [Ixxillikor](../../areas/zon/ixxillikor.zon) | [Combat Mind](../../src/classes/psionics.c#L1094) (#163) | 3 | 1 | Mental discipline fits a neogi settlement with an enslaved workforce and umber-hulk guards. |
| 44 | [The Underworld](../../areas/zon/underworld.zon) | [Globe Of Darkness](../../src/magic/magic.c#L17667) (#302) | 3 | 1 | A carried darkness sphere fits the deep underground river and cavern settlement. Preserve light exclusions; explicit origin IDs separate the Underworld zones and ambiguous legacy tags stay HP-only. |
| 55 | [The Tharnadian Ruin](../../areas/zon/tharnadian_ruin.zon) | [Holy Light](../../src/magic/magic.c#L17597) (#615) | 3 | 1 | A guiding holy light fits a ruined city populated by restless spirits. Preserve the existing light/darkness exclusions. |
| 62 | [The Cimmerian Nomad Encampment](../../areas/zon/nomads.zon) | [Wolfspeed](../../src/magic/smagic.c#L2683) (#193) | 3 | 1 | A larger movement pool suits the nomads' wagons and travel across the plains. |
| 71 | [The Ruins of Turolopolis](../../areas/zon/willem.zon) | [Detect Good](../../src/magic/magic.c#L9283) (#91) | 3 | 1 | The holy shaman provides a concrete religious theme for sensing good among the ruined streets. |
| 76 | [Bastine Castle](../../areas/zon/bastine.zon) | [Pulchritude](../../src/magic/magic.c#L8075) (#347) | 3 | 1 | A royal court headed by a king and queen suits a charisma/appearance bonus. |
| 78 | [Vargan II](../../areas/zon/v2.zon) | [Infravision](../../src/magic/magic.c#L22089) (#106) | 3 | 1 | Heat-oriented vision fits the ancient dark passages and their underground inhabitants. |
| 132 | [The Twin Towers](../../areas/zon/ttowers.zon) | [Displacement](../../src/classes/psionics.c#L2206) (#169) | 3 | 1 | A magical defensive image fits the towers' magic shop, mirrors, and magically reinforced passages. |
| 135 | [Twin Towers Forest](../../areas/zon/twin_towers_forest.zon) | [Farsee](../../src/classes/skills.c#L1577) (#53) | 3 | 1 | Long sight suits scouting the forest paths inhabited by wolves and pixies. |
| 163 | [A Dark and Twisted Wood](../../areas/zon/twstwd.zon) | [Slow Poison](../../src/magic/magic.c#L17814) (#130) | 3 | 1 | Slowing poison directly fits the poisonous ivy and dangerous vegetation. |
| 204 | [Neverwind Valley](../../areas/zon/pyramid.zon) | [Sense Life](../../src/magic/magic.c#L12385) (#44) | 3 | 1 | Sensing living creatures contrasts with the valley's skeletons, zombies, spectres, and wraiths. Its authored title fix is in the PR stack; final gameplay validation remains. |
| 209 | [Mountain Tracts of the Untamed](../../areas/zon/mountaintracks.zon) | [Adrenaline Control](../../src/classes/psionics.c#L412) (#157) | 5 | 1 | Physical readiness fits the steep mountain trails, caves, and untamed predators. |
| 236 | [Malch'Hor Ganl the Goblin City](../../areas/zon/malch.zon) | [Agility](../../src/classes/skills.c#L2053) (#584) | 3 | 1 | Agility fits goblin thieves moving through narrow tunnels and a crowded underground city. |
| 281 | [Verspin](../../areas/zon/verspin.zon) | [Serendipity](../../src/magic/magic.c#L8284) (#352) | 3 | 1 | Luck fits a trading town with gem shops, merchants, and a trade master. |
| 344 | [Defense of Longhollow](../../areas/zon/long.zon) | [Battletide](../../src/magic/magic.c#L16594) (#395) | 5 | 1 | A martial accuracy/damage bonus fits the fighting templars, wounded knight, and opposing guards. |
| 352 | [The City of Newhaven](../../areas/zon/newhaven.zon) | [Detect Evil](../../src/magic/magic.c#L9246) (#90) | 3 | 1 | Detecting evil fits a city with knights and their corrupted zombie, vampire, wraith, and lich counterparts. |
| 358 | [Abandoned Elven Homestead](../../areas/zon/elvish.zon) | [Sense Spirit](../../src/magic/smagic.c#L4244) (#211) | 3 | 1 | Spirit detection directly fits the spirit of an Elven protector in the abandoned homestead. |
| 404 | [Golden Hall of the Crown](../../areas/zon/gold_hal.zon) | [Virtue](../../src/magic/magic.c#L6927) (#515) | 3 | 1 | Virtue fits the fortress's knight trainees and their master teacher. Preserve the native good/non-good and evil/non-evil combat conditions, including neutral targets. |
| 422 | [Tribal Forest](../../areas/zon/tribal.zon) | [Guardian Spirits](../../src/magic/smagic.c#L208) (#579) | 6 | 1 | Ancestral protection fits the tribal shaman and young shaman apprentice. **Shaman wearers only**, as required by the existing spell. |
| 429 | [Drustl's Yerdonia Enslaved](../../areas/zon/raxthan.zon) | [Protection From Good](../../src/magic/magic.c#L11004) (#81) | 3 | 1 | An evil-sided ward fits the slave master, witch doctor, assassins, and oppressive Raxian guards. |
| 430 | [Prison of Fort Boyard](../../areas/zon/prisonb.zon) | [Protection From Acid](../../src/magic/magic.c#L21936) (#105) | 3 | 1 | Acid protection fits the prison's black dragon and its broader collection of dangerous dragons. |
| 431 | [The Ship Yards](../../areas/zon/shipy.zon) | [Enhance Dexterity](../../src/classes/psionics.c#L2564) (#176) | 3 | 1 | Precise hands and footwork fit shipyard work, dockside gear, and harbor guards. |
| 435 | [Temple of the Earth](../../areas/zon/earth.zon) | [Fortitude](../../src/magic/magic.c#L6345) (#348) | 3 | 1 | Constitution and resilience fit the mountain temple, duergar guardians, and earth golems. |
| 437 | [Lost City of Tikitzopl](../../areas/zon/tikit.zon) | [Slow Poison](../../src/magic/magic.c#L17814) (#130) | 3 | 1 | Slowing poison directly fits the Snake Pit and the explicitly poisonous fangs of its inhabitants. |
| 550 | [The City of Winterhaven](../../areas/zon/wh.zon) | [Comprehend Languages](../../src/magic/magic.c#L17843) (#132) | 3 | 1 | Understanding languages fits a major city whose authored rooms explicitly handle ambassadors to Alatorin. |
| 570 | [The Trakkia Mountains](../../areas/zon/trakkia.zon) | [Enhance Constitution](../../src/classes/psionics.c#L2650) (#178) | 3 | 1 | Constitution fits the rugged foothills and mountain tribes. |
| 588 | [The Realm of Barovia Continued](../../areas/zon/barovia2.zon) | [Lifelust](../../src/magic/magic.c#L7776) (#321) | 3 | 1 | Lifelust fits the bloodthirsty werewolves, witches, and Vistani of Barovia's continuation, echoing the main area's planned theme without sharing set identity. |
| 660 | [Ashrumite Village](../../areas/zon/ashrumite.zon) | [Detect Illusion](../../src/classes/sillusionist.c#L1797) (#414) | 3 | 1 | Seeing through illusions directly fits the village's illusionist guildmaster and magical guilds. |
| 666 | [City of Torrhan](../../areas/zon/torrhan.zon) | [Warring Zeal](../../src/magic/magic.c#L25432) (#680) | 3 | 1 | Battle accuracy fits the city's tower guards, elite guards, and captain of the guards. |
| 712 | [The Scorched Valley](../../areas/zon/scorchvalley.zon) | [Protection From Gas](../../src/magic/magic.c#L21917) (#104) | 3 | 1 | Gas protection fits the opening description's choking fumes from burning vegetation and bodies. |
| 752 | [Northern Lakes and Settlements](../../areas/zon/nlakes.zon) | [Protection From Cold](../../src/classes/skills.c#L2308) (#97) | 3 | 2 | Cold protection directly matches the icy footpaths and northern settlements. The environmental fit takes priority over its existing two homes. |
| 775 | [The Mountain Valley of Dawndale](../../areas/zon/airshipgrave.zon) | [Hawkvision](../../src/magic/smagic.c#L3281) (#204) | 3 | 1 | Long sight suits scouts and guards moving along high mountain trails around an elven settlement. |
| 784 | [The Twin Keeps of Devastated Tharnadia](../../areas/zon/caertannad.zon) | [Divine Fury](../../src/magic/magic.c#L22267) (#310) | 3 | 1 | Religious battle fury fits the rival fortified keeps, smashed altars, and streets dedicated to the duergar god Grunthorigard. |
| 808 | [Ceothia](../../areas/zon/ceothia.zon) | [Enhance Agility](../../src/classes/skills.c#L944) (#177) | 3 | 1 | Agility fits present-day Ceothia's shadow thieves and moonstone thieves. Separate explicit era origins are implemented; ambiguous legacy tags stay HP-only. |
| 811 | [Ceothia](../../areas/zon/ceopast.zon) | [Protection From Animals](../../src/magic/magic.c#L21864) (#383) | 3 | 1 | Protection from animals directly fits the wolf packs in Ceothia's densely forested past. Separate explicit era origins are implemented; ambiguous legacy tags stay HP-only. |
| 814 | [Ceothia](../../areas/zon/ceofutur.zon) | [Vapor Strike](../../src/classes/ethermancer.c#L1134) (#467) | 3 | 1 | A vapor-themed accuracy bonus fits future Ceothia's smoky, scorched camps and battle-scarred landscape. Separate explicit era origins are implemented; ambiguous legacy tags stay HP-only. |
| 820 | [Jindon the Deathwood Forest](../../areas/zon/jin.zon) | [Detect Illusion](../../src/classes/sillusionist.c#L1797) (#414) | 3 | 1 | Seeing through tricks fits a carnival with performers, magical merchandise, and conjuring entertainments. |
| 825 | [Myrabolus](../../areas/zon/mira.zon) | [Sense Holiness](../../src/magic/magic.c#L7067) (#316) | 3 | 1 | Sensing holiness directly fits the holy knights, celestial white dragon, and Home of the Holy. |
| 828 | [The Motte and Bailey of Duke Delwyn](../../areas/zon/delwyn.zon) | [Enhance Armor](../../src/classes/psionics.c#L2459) (#174) | 3 | 1 | Improved armor fits a fortified motte and bailey with a master bladesmith and a guard garrison. |
| 883 | [The Charcoal Palace](../../areas/zon/firep.zon) | [Energy Containment](../../src/classes/psionics.c#L2405) (#173) | 3 | 1 | Containing elemental energy fits a palace surrounded by molten rock, sulfur, and fire minions. |
| 888 | [Menden-on-the-Deep](../../areas/zon/menden.zon) | [Mage Flame](../../src/magic/magic.c#L17626) (#297) | 3 | 1 | A small magical light fits the village magus and the explicitly described fire-magic experiments. Preserve light/darkness exclusions. |
| 889 | [Fishermans Wharf](../../areas/zon/fishermans_wharf.zon) | [Sense Follower](../../src/magic/magic.c#L24629) (#279) | 3 | 1 | Finding followers fits keeping track of companions around a working wharf, dirty piers, and coastal paths. |
| 920 | [The Ruins of Undermountain](../../areas/zon/undermountain.zon) | [Displacement](../../src/classes/psionics.c#L2206) (#169) | 3 | 1 | A shifting defense fits a sprawling dungeon of hidden rooms, shadowbeasts, and dangerous corridors. |
| 940 | [The Maze of Undead Army](../../areas/zon/maze_are.zon) | [Protection From Evil](../../src/magic/magic.c#L10975) (#34) | 3 | 1 | Protection from evil fits the old graveyard, soulless guardians, lich priest, and undead army. |
| 947 | [The Deep Ravine of Passage](../../areas/zon/minopass.zon) | [Farsee](../../src/classes/skills.c#L1577) (#53) | 3 | 1 | Long sight directly suits watching across a deep ravine and its rocky mountain passes. |
| 950 | [Mistywood](../../areas/zon/mistywood.zon) | [Vapor Armor](../../src/classes/ethermancer.c#L104) (#452) | 3 | 1 | Mist-shaped armor directly matches the misty woodland and river setting. |
| 968 | [Dirk'nspire Stronghold](../../areas/zon/dirkn.zon) | [Lodestone Vision](../../src/magic/magic.c#L12484) (#617) | 3 | 1 | Mineral detection fits the Deep Dwarves and the stronghold's underground rock tunnels. |
| 969 | [Troll Caves](../../areas/zon/troll_caves.zon) | [Enhance Strength](../../src/classes/skills.c#L932) (#175) | 3 | 1 | Strength fits the troll inhabitants and their cavern stronghold. |
| 970 | [IceCrag Castle](../../areas/zon/icecrag.zon) | [Enhance Constitution](../../src/classes/psionics.c#L2650) (#178) | 3 | 1 | Hardiness fits a cold castle staffed by patrol guards, an Ice Priest, and siege defenders. |
| 979 | [The Minizones of the Surface](../../areas/zon/surfacemini.zon) | [Serendipity](../../src/magic/magic.c#L8284) (#352) | 3 | 1 | A luck bonus suits a collection of small adventures and unusual encounters, including Gorblaat's Cave. |
| 985 | [The Bandit Canyons](../../areas/zon/bandit.zon) | [Enhance Dexterity](../../src/classes/psionics.c#L2564) (#176) | 3 | 1 | Dexterous movement fits the bandits, canyon ambushes, and scrub-covered campsites. |
| 990 | [Neverwinter Woods](../../areas/zon/moria.zon) | [Scent Of The Bloodhound](../../src/magic/smagic.c#L2353) (#517) | 3 | 1 | Scent-based tracking fits a woodland expedition among the elves. Its authored title fix is in the PR stack; final gameplay validation remains. |
| 994 | [Varathorn Keep](../../areas/zon/kastle.zon) | [Protection From Evil](../../src/magic/magic.c#L10975) (#34) | 3 | 1 | Protection from evil fits ruined halls occupied by zombie guards, skeletal knights, and a vampire guardian. |
| 995 | [Cloud Giant Kingdom](../../areas/zon/cldgt.zon) | [Enhance Strength](../../src/classes/skills.c#L932) (#175) | 3 | 1 | Strength directly matches the cloud giant warriors and heroes. |
| 1300 | [Vecna's Tomb](../../areas/zon/vecna.zon) | [Sense Spirit](../../src/magic/smagic.c#L4244) (#211) | 3 | 1 | Spirit detection fits Vecna's tomb, its shadows, death knights, and barrow guardians. |
| 1312 | [Grumbar's Domain](../../areas/zon/earthp.zon) | [Lodestone Vision](../../src/magic/magic.c#L12484) (#617) | 3 | 1 | Mineral detection directly fits Grumbar's earth realm and its huge geode dragon. |
| 1316 | [The Tempest Court](../../areas/zon/airp.zon) | [Protection From Lightning](../../src/classes/skills.c#L2347) (#98) | 3 | 1 | Lightning protection directly matches the Heart of the Storm and the Tempest Court. |
| 1389 | [The Ancient Halls of Ironstar](../../areas/zon/lornecro.zon) | [Sense Life](../../src/magic/magic.c#L12385) (#44) | 3 | 1 | Sensing living creatures contrasts with the Ironstar halls' guardian wights, skeletal defenders, and apprentice necromancer. |
| 1390 | [Plane of Fire, Brass](../../areas/zon/brass.zon) | [Protection From Fire](../../src/classes/skills.c#L2301) (#96) | 3 | 1 | Fire protection directly matches the City of Brass, efreeti, fire giants, and Imix Avenue. |

## Effect homes after both passes

Only the 50 effects used by the reuse pass are shown. Baseline homes refer to
the original 115-row catalog; the two initial planning passes remain visible.
The wider and final columns reconcile to the installed implementation catalog.

| Effect (game ID) | Baseline homes | Initial proposed homes | Additional proposed homes | After initial two passes | Wider additions | Final catalog homes |
|---|---:|---:|---:|---:|---:|---:|
| [Adrenaline Control](../../src/classes/psionics.c#L412) (#157) | 0 | 1 | 1 | 2 | 1 | 3 |
| [Agility](../../src/classes/skills.c#L2053) (#584) | 1 | 0 | 1 | 2 | 0 | 2 |
| [Battletide](../../src/magic/magic.c#L16594) (#395) | 0 | 1 | 1 | 2 | 1 | 3 |
| [Combat Mind](../../src/classes/psionics.c#L1094) (#163) | 0 | 1 | 1 | 2 | 2 | 4 |
| [Comprehend Languages](../../src/magic/magic.c#L17843) (#132) | 0 | 1 | 1 | 2 | 3 | 5 |
| [Detect Evil](../../src/magic/magic.c#L9246) (#90) | 0 | 1 | 1 | 2 | 1 | 3 |
| [Detect Good](../../src/magic/magic.c#L9283) (#91) | 0 | 1 | 1 | 2 | 1 | 3 |
| [Detect Illusion](../../src/classes/sillusionist.c#L1797) (#414) | 0 | 1 | 2 | 3 | 3 | 6 |
| [Dexterity](../../src/magic/magic.c#L11563) (#73) | 0 | 1 | 1 | 2 | 1 | 3 |
| [Displacement](../../src/classes/psionics.c#L2206) (#169) | 0 | 1 | 2 | 3 | 1 | 4 |
| [Divine Fury](../../src/magic/magic.c#L22267) (#310) | 0 | 1 | 1 | 2 | 1 | 3 |
| [Energy Containment](../../src/classes/psionics.c#L2405) (#173) | 0 | 1 | 1 | 2 | 1 | 3 |
| [Enhance Agility](../../src/classes/skills.c#L944) (#177) | 1 | 0 | 1 | 2 | 0 | 2 |
| [Enhance Armor](../../src/classes/psionics.c#L2459) (#174) | 0 | 1 | 1 | 2 | 2 | 4 |
| [Enhance Constitution](../../src/classes/psionics.c#L2650) (#178) | 0 | 1 | 2 | 3 | 2 | 5 |
| [Enhance Dexterity](../../src/classes/psionics.c#L2564) (#176) | 0 | 1 | 2 | 3 | 3 | 6 |
| [Enhance Strength](../../src/classes/skills.c#L932) (#175) | 1 | 0 | 2 | 3 | 2 | 5 |
| [Farsee](../../src/classes/skills.c#L1577) (#53) | 1 | 0 | 2 | 3 | 2 | 5 |
| [Fortitude](../../src/magic/magic.c#L6345) (#348) | 0 | 1 | 1 | 2 | 5 | 7 |
| [Globe Of Darkness](../../src/magic/magic.c#L17667) (#302) | 0 | 1 | 1 | 2 | 1 | 3 |
| [Guardian Spirits](../../src/magic/smagic.c#L208) (#579) | 0 | 1 | 1 | 2 | 0 | 2 |
| [Hawkvision](../../src/magic/smagic.c#L3281) (#204) | 0 | 1 | 1 | 2 | 2 | 4 |
| [Holy Light](../../src/magic/magic.c#L17597) (#615) | 0 | 1 | 1 | 2 | 0 | 2 |
| [Infravision](../../src/magic/magic.c#L22089) (#106) | 0 | 1 | 1 | 2 | 2 | 4 |
| [Lifelust](../../src/magic/magic.c#L7776) (#321) | 0 | 1 | 1 | 2 | 0 | 2 |
| [Lodestone Vision](../../src/magic/magic.c#L12484) (#617) | 0 | 1 | 2 | 3 | 2 | 5 |
| [Mage Flame](../../src/magic/magic.c#L17626) (#297) | 0 | 1 | 1 | 2 | 0 | 2 |
| [Phantom Armor](../../src/classes/sillusionist.c#L131) (#400) | 0 | 1 | 1 | 2 | 2 | 4 |
| [Protection From Acid](../../src/magic/magic.c#L21936) (#105) | 0 | 1 | 1 | 2 | 1 | 3 |
| [Protection From Animals](../../src/magic/magic.c#L21864) (#383) | 0 | 1 | 1 | 2 | 3 | 5 |
| [Protection From Evil](../../src/magic/magic.c#L10975) (#34) | 0 | 1 | 2 | 3 | 2 | 5 |
| [Protection From Fire](../../src/classes/skills.c#L2301) (#96) | 1 | 0 | 1 | 2 | 3 | 5 |
| [Protection From Gas](../../src/magic/magic.c#L21917) (#104) | 0 | 1 | 1 | 2 | 3 | 5 |
| [Protection From Good](../../src/magic/magic.c#L11004) (#81) | 0 | 1 | 1 | 2 | 2 | 4 |
| [Protection From Lightning](../../src/classes/skills.c#L2347) (#98) | 1 | 0 | 1 | 2 | 0 | 2 |
| [Pulchritude](../../src/magic/magic.c#L8075) (#347) | 0 | 1 | 1 | 2 | 1 | 3 |
| [Scent Of The Bloodhound](../../src/magic/smagic.c#L2353) (#517) | 0 | 1 | 1 | 2 | 2 | 4 |
| [Sense Follower](../../src/magic/magic.c#L24629) (#279) | 0 | 1 | 1 | 2 | 2 | 4 |
| [Sense Holiness](../../src/magic/magic.c#L7067) (#316) | 0 | 1 | 1 | 2 | 3 | 5 |
| [Sense Life](../../src/magic/magic.c#L12385) (#44) | 0 | 1 | 2 | 3 | 4 | 7 |
| [Sense Spirit](../../src/magic/smagic.c#L4244) (#211) | 0 | 1 | 2 | 3 | 5 | 8 |
| [Serendipity](../../src/magic/magic.c#L8284) (#352) | 0 | 1 | 2 | 3 | 2 | 5 |
| [Slow Poison](../../src/magic/magic.c#L17814) (#130) | 0 | 1 | 2 | 3 | 0 | 3 |
| [Vapor Armor](../../src/classes/ethermancer.c#L104) (#452) | 0 | 1 | 1 | 2 | 0 | 2 |
| [Vapor Strike](../../src/classes/ethermancer.c#L1134) (#467) | 0 | 1 | 1 | 2 | 0 | 2 |
| [Virtue](../../src/magic/magic.c#L6927) (#515) | 0 | 1 | 1 | 2 | 0 | 2 |
| [Warring Zeal](../../src/magic/magic.c#L25432) (#680) | 0 | 1 | 1 | 2 | 2 | 4 |
| [Wolfspeed](../../src/magic/smagic.c#L2683) (#193) | 0 | 1 | 1 | 2 | 1 | 3 |
| [Protection From Cold](../../src/classes/skills.c#L2308) (#97) | 2 | 0 | 1 | 3 | 0 | 3 |
| [Water Breathing](../../src/classes/skills.c#L1571) (#85) | 4 | 0 | 1 | 5 | 2 | 7 |

## Remaining work

**All 183 additions now have catalog rows with recorded effects and requirements.** The seven
special identity/title repairs are implemented in the current PR stack. Their
catalog rows and final gameplay journeys remain open; the main plan records the
existing fixture and persistence evidence.

| Zone ID | Zone | Proposed effect | Current implementation gate |
|---:|---|---|---|
| 13 | [Braddistock Mansion](../../areas/zon/braddistock.zon) | [Phantom Armor](../../src/classes/sillusionist.c#L131) (#400) | Explicit #13 origin and ambiguous legacy grouping implemented; catalog/actual gameplay gate pending. |
| 44 | [The Underworld](../../areas/zon/underworld.zon) | [Globe Of Darkness](../../src/magic/magic.c#L17667) (#302) | Explicit #44 origin and ambiguous legacy grouping implemented; catalog/actual gameplay gate pending. |
| 204 | [Neverwind Valley](../../areas/zon/pyramid.zon) | [Sense Life](../../src/magic/magic.c#L12385) (#44) | Authored color/title fix and isolated world regeneration verified; final named-drop/activation/reload gate pending. |
| 808 | [Ceothia](../../areas/zon/ceothia.zon) | [Enhance Agility](../../src/classes/skills.c#L944) (#177) | Separate explicit era origin and ambiguous legacy grouping implemented; catalog/actual gameplay gate pending. |
| 811 | [Ceothia](../../areas/zon/ceopast.zon) | [Protection From Animals](../../src/magic/magic.c#L21864) (#383) | Separate explicit era origin and ambiguous legacy grouping implemented; catalog/actual gameplay gate pending. |
| 814 | [Ceothia](../../areas/zon/ceofutur.zon) | [Vapor Strike](../../src/classes/ethermancer.c#L1134) (#467) | Separate explicit era origin and ambiguous legacy grouping implemented; catalog/actual gameplay gate pending. |
| 990 | [Neverwinter Woods](../../areas/zon/moria.zon) | [Scent Of The Bloodhound](../../src/magic/smagic.c#L2353) (#517) | Authored color/title fix and isolated world regeneration verified; final named-drop/activation/reload gate pending. |

## Existing plain-title set areas

The four existing set areas below are **independent playable sets**, rather than
legacy-only records. Their authored titles now have the same narrow `&+g…&n`
color treatment used for #204/#990, preserving every visible character. This
restores the existing generator's title eligibility; its rolls and formulas are
unchanged. No new catalog row or effect tier is needed for these four areas.

| ID / authored area | Access and repeatable encounter evidence | Existing spell tiers retained |
|---|---|---|
| #87 [Gibberling King](../../areas/zon/gibber.zon) | Underdark `820717 E → 8700` (also `820318 S → 8700`), then down to 8701. Key #8739 resets on the floor in 8701 and unlocks the east door to 8702; mob #8709 (level 20) resets there. | Spirit Ward at 3; Haste at 5. |
| #370 [Crystalspyre](../../areas/zon/vrzawild.zon) | Surface `523536 W → 37090`, with interior routes to repeatable dire wolves, including #37001 (level 17) in 37001. These mountain rooms are area terrain, not impassable map-marker mountains. | Endurance at 3. |
| #676 [Taliccicopiid](../../areas/zon/thri.zon) | Surface `603653 W → 67600`; the ravine connects into the occupied complex. Flesh-eating ant #67656 (level 4) resets in 67602, among the many ordinary encounters. | Endurance at 4. |
| #824 [Temple of the Sun](../../areas/zon/suntmpl.zon) | Surface `554128 E → 82493`; doe #82428 (level 20) resets directly at this entry. Deeper repeatable encounters also exist; eligibility does not depend on defeating the temple boss. | Vitality at 6. |

Room/exit sources are the matching files under `areas/wld/`, plus the active
surface/Underdark maps. Each witness is a non-shop mobile in a non-guild combat
room, outside a recognized hometown cap. Normal `convertMob()` supplies positive
XP even when the authored XP is zero. Ordinary appropriately leveled players
can pass the unchanged drop/naming guards; no staff movement or guessed origin
is required. These are authored-source access/encounter checks, not a claim of
completed live walk/kill/save journeys.

Focused verification reads the actual four authored titles into the real random
equipment generator and checks successful naming, failed naming, fixed-material
exclusion and origin identity under ASan/UBSan. The original 1,480 equipment cases
and RNG sentinels remain byte-for-byte unchanged. Origin tests cover all four
IDs, legacy visible tags and clones; real membership/tier dispatch verifies
2/3/4/5/6 pieces and HP cleanup. An isolated `make world` differs only in these
four header strings; all resets and the other six generated outputs are identical.
The broader 135-record review and final gameplay/storage gates remain open.

## Wider area review and additional assignments
The fresh active world has 354 records. The 115 original catalog rows are
retained, and the owner-reviewed 104-zone queue remains unchanged. The remaining
135 records are classified below: **79 independent additions and 56 exclusions**.
No shared-origin grouping is introduced. Separate zone IDs, including #300 and
#1350, keep separate piece counts even when they reuse the same effect.

The resulting target is **298 catalog rows, 389 effect tiers and 106 distinct
effect IDs**: 115 old rows plus 183 additions, each with one tier. Among the 183
additions, 175 need three pieces, six need five and two need six. The initial
42+62 pairings and their thresholds are retained; the wider additions reuse only
the already-qualified 50-effect pool. The home counts in the earlier table describe
the original two passes; the home-count table also records the wider additions and final totals.

Access evidence uses native mortal hometown/tutorial arrivals, explicit planar
destinations, authored exits and placed teleport objects. Reset-locked pickproof
doors require a reachable reset key; blocked walls require a reachable native
switch. Openable/pickable/secret doors remain legitimate routes. Map mountains,
closed/private zones and unreachable components are not treated as public paths.
This is an authored-source review, not a claim that every route was live-playtested.

Full Ailvio/Wutvr outposts have ordinary combat encounters and native entry through
the Life/Chaos guide and stream. A level-11 resident can hunt a level-5 wolf within
the unchanged level-gap rule and can roll a zone name; these full outposts are
included. The seven-room creation introductions remain onboarding infrastructure.

`ZONE_SAFE` is not a blanket PvM exclusion: normal kill/attack admission checks
`ROOM_SAFE` through `CanDoFightMove`. Some commands and reward systems separately
check `ZONE_SAFE`. Forgotten Forest is included; Wandering Fields is excluded for
its staging purpose. The executable golden regression checks this distinction.

### The 79 wider-review additions

Witnesses below are reset mobile/room pairs reachable through the recorded entry,
apart from the explicitly described Orog dispersal case. They exclude shopkeepers,
guild/safe combat rooms and hometown mobs above level 25. Normal mobile conversion
supplies positive XP; ACT_IGNORE/`_ignore_` exceptions retain their authored XP.

| ID | Area | Assigned effect | Pieces | Authored access, encounter and theme |
|---:|---|---|---:|---|
| 16 | [Truktakyagyo](../../areas/zon/truk.zon) | [Dexterity](../../src/magic/magic.c#L11563) (#73) | 3 | 70198 exit#0 → 1655; mobile #1602 at 1604. Goblin settlement: nimble guards and sentries. |
| 34 | [The Minor Plane of Planitude](../../areas/zon/flind.zon) | [Protection From Good](../../src/magic/magic.c#L11004) (#81) | 3 | 829678 exit#0 → 3475; mobile #3407 at 3400. Infernal/flind plane: protection from good fits its hostile priesthood. |
| 48 | [The Monestary of Tranquility](../../areas/zon/tchan.zon) | [Sense Holiness](../../src/magic/magic.c#L7067) (#316) | 3 | 513140 exit#1 → 4800; mobile #4800 at 4808. Monastery and its priest/guard encounters: sense holiness. |
| 57 | [Mini Zones](../../areas/zon/minizones.zon) | [Comprehend Languages](../../src/magic/magic.c#L17843) (#132) | 3 | 518898 exit#2 → 5735; mobile #5709 at 5735. Multiple small settlements and encounters: comprehension utility. |
| 63 | [The Shadow Forest](../../areas/zon/mist.zon) | [Detect Illusion](../../src/classes/sillusionist.c#L1797) (#414) | 3 | 628063 exit#3 → 6300; mobile #6307 at 6300. Shadow forest: seeing through deceptive appearances. |
| 64 | [The Bugger Caves](../../areas/zon/bugger.zon) | [Infravision](../../src/magic/magic.c#L22089) (#106) | 3 | 807099 exit#2 → 6400; mobile #6400 at 6400. Underground bugger caves: infravision. |
| 65 | [The Shaughin Settlement](../../areas/zon/shaughin.zon) | [Water Breathing](../../src/classes/skills.c#L1571) (#85) | 3 | 804249 exit#2 → 6500; mobile #6500 at 6502. Underwater Shaughin settlement: water breathing. |
| 66 | [The Shaughin Hunting Grounds](../../areas/zon/shaughin2.zon) | [Hawkvision](../../src/magic/smagic.c#L3281) (#204) | 3 | 6504 object#6500 → 6600; mobile #6600 at 6603. Shaughin hunting grounds: hawkvision for the hunt. |
| 70 | [Traoul's Lair](../../areas/zon/traoul.zon) | [Warring Zeal](../../src/magic/magic.c#L25432) (#680) | 3 | 1622 exit#0 → 7000; mobile #7000 at 7000. Raider lair: martial accuracy from Warring Zeal. |
| 81 | [The Temple of Laduguer](../../areas/zon/temple_laduguer.zon) | [Protection From Good](../../src/magic/magic.c#L11004) (#81) | 3 | 827455 exit#1 → 8100; mobile #8102 at 8103. Laduguer’s hostile temple: protection from good. |
| 84 | [The Old Graveyard](../../areas/zon/grave.zon) | [Sense Life](../../src/magic/magic.c#L12385) (#44) | 3 | 593389 exit#0 → 8400; mobile #8406 at 8404. Undead graveyard: sense the living among the dead. |
| 89 | [Ogre Raiders](../../areas/zon/raiders.zon) | [Enhance Strength](../../src/classes/skills.c#L932) (#175) | 3 | 593506 exit#0 → 8900; mobile #8905 at 8902. Ogre raiders: enhanced physical strength. |
| 92 | [The Temple of Lizizania](../../areas/zon/asylum.zon) | [Sense Holiness](../../src/magic/magic.c#L7067) (#316) | 3 | 616249 exit#0 → 9288; mobile #9209 at 9201. Lizizania’s temple encounters: sense holiness. |
| 101 | [The Mushroom Forest](../../areas/zon/mush1.zon) | [Protection From Gas](../../src/magic/magic.c#L21917) (#104) | 3 | 856059 exit#3 → 10100; mobile #10108 at 10223. Mushroom forest: protection from fungal gas. |
| 107 | [Black Tunnels](../../areas/zon/black_tunnels.zon) | [Infravision](../../src/magic/magic.c#L22089) (#106) | 3 | 10693 exit#0 → 10700; mobile #10700 at 10706. Black underground tunnels: infravision. |
| 109 | [Ant Forest](../../areas/zon/ants.zon) | [Scent Of The Bloodhound](../../src/magic/smagic.c#L2353) (#517) | 3 | 526267 exit#1 → 10900; mobile #10900 at 10901. Ant trails and forest tracking: bloodhound scent. |
| 114 | [The Goblin Camp](../../areas/zon/goblincamp.zon) | [Enhance Dexterity](../../src/classes/psionics.c#L2564) (#176) | 3 | 617373 exit#0 → 11400; mobile #11400 at 11400. Goblin camp: nimble combatants and enhanced dexterity. |
| 115 | [Ghore](../../areas/zon/ghore.zon) | [Fortitude](../../src/magic/magic.c#L6345) (#348) | 3 | Native hometown/tutorial arrival 11703; mobile #11505 at 11504. Ghore’s hardy inhabitants: constitution from Fortitude. |
| 120 | [Lava Tubes](../../areas/zon/lava_tubes.zon) | [Protection From Fire](../../src/classes/skills.c#L2301) (#96) | 3 | 20973 exit#4 → 12131; mobile #12004 at 12005. Lava tubes: protection from fire. |
| 127 | [Skulldrach](../../areas/zon/skulldrach.zon) | [Enhance Armor](../../src/classes/psionics.c#L2459) (#174) | 3 | 632637 exit#0 → 12859; mobile #12703 at 12701. Skulldrach settlement and guards: enhanced armor. |
| 180 | [The Lost Realms of Shadowfall](../../areas/zon/wolfen.zon) | [Sense Spirit](../../src/magic/smagic.c#L4244) (#211) | 3 | 620706 exit#2 → 18000; mobile #18012 at 18035. Shadowfall’s inhabitants and spirits: sense spirit. |
| 187 | [BogenTok](../../areas/zon/bogentok.zon) | [Combat Mind](../../src/classes/psionics.c#L1094) (#163) | 3 | 812663 exit#3 → 18700; mobile #18720 at 18700. BogenTok’s military inhabitants: Combat Mind. |
| 190 | [The Gagga'Jobo Cave System](../../areas/zon/goblincave.zon) | [Detect Illusion](../../src/classes/sillusionist.c#L1797) (#414) | 3 | 842047 exit#1 → 19000; mobile #19009 at 19000. Goblin cave system: detect illusion in concealed tunnels. |
| 194 | [Githyanki Hometown](../../areas/zon/gith_ht.zon) | [Adrenaline Control](../../src/classes/psionics.c#L412) (#157) | 5 | Native hometown/tutorial arrival 19428; mobile #19409 at 19423. Githyanki psionic hometown: Adrenaline Control. |
| 198 | [Astral Plane, Side Areas](../../areas/zon/astral_areas.zon) | [Displacement](../../src/classes/psionics.c#L2206) (#169) | 3 | 19755 exit#2 → 19826; mobile #19900 at 19826. Astral side areas: displacement. |
| 199 | [Astral Plane, Tiamat](../../areas/zon/astral_tiamat.zon) | [Protection From Gas](../../src/magic/magic.c#L21917) (#104) | 3 | 19800 exit#0 → 19928; mobile #19760 at 19928. Tiamat’s astral dragon encounters: gas protection. |
| 206 | [Barrow of the Quiosho](../../areas/zon/elftomb.zon) | [Sense Spirit](../../src/magic/smagic.c#L4244) (#211) | 3 | 609100 exit#1 → 20600; mobile #20600 at 20601. Barrow and its dead: sense spirit. |
| 241 | [the Mushroom Caverns](../../areas/zon/mushroom_caverns.zon) | [Protection From Gas](../../src/magic/magic.c#L21917) (#104) | 3 | 17746 exit#2 → 24108; mobile #24107 at 24102. Mushroom caverns: fungal gas protection. |
| 292 | [Ailvio, Duris Newbie Outpost](../../areas/zon/newbie.zon) | [Fortitude](../../src/magic/magic.c#L6345) (#348) | 3 | 22806 stream_of_life after guide conversation → 29201; mobile #29265 at 29228. Full Ailvio tutorial outpost: a small constitution blessing for developing adventurers. |
| 300 | [The Underworld](../../areas/zon/underworld3.zon) | [Globe Of Darkness](../../src/magic/magic.c#L17667) (#302) | 3 | 26272 exit#5 → 30000; mobile #30027 at 30004. Independent Underworld cave encounters: darkness. |
| 304 | [Ard'gral, plane of dreams](../../areas/zon/ardgral.zon) | [Phantom Armor](../../src/classes/sillusionist.c#L131) (#400) | 3 | 83342 object#83141 → 30453; mobile #30401 at 30422. Plane of dreams and nightmares: phantom armor. |
| 337 | [Miaeril Village](../../areas/zon/mril.zon) | [Comprehend Languages](../../src/magic/magic.c#L17843) (#132) | 3 | 522257 exit#3 → 33764; mobile #33714 at 33710. Miaeril village and its social encounters: comprehension. |
| 340 | [The Basin Wastes](../../areas/zon/basin_wa.zon) | [Fortitude](../../src/magic/magic.c#L6345) (#348) | 3 | 612059 exit#5 → 34000; mobile #34005 at 34002. Harsh basin wastes: constitution and endurance. |
| 362 | [Llzazan Ghetto of Arachdrathos](../../areas/zon/llzazan.zon) | [Sense Follower](../../src/magic/magic.c#L24629) (#279) | 3 | Native hometown/tutorial arrival 36329; mobile #36225 at 36200. Urban ghetto and followers: Sense Follower. |
| 410 | [Dreggan Woods](../../areas/zon/dreggan_wood.zon) | [Sense Life](../../src/magic/magic.c#L12385) (#44) | 3 | 12480 exit#3 → 41001; mobile #41003 at 41009. Dreggan woodland encounters: sense life. |
| 413 | [Southern Coastal Highway](../../areas/zon/highway.zon) | [Farsee](../../src/classes/skills.c#L1577) (#53) | 3 | 530849 exit#2 → 41837; mobile #41354 at 41307. Coastal road with dedicated bandit/creature encounters: farsee. |
| 425 | [Lair of the Purple Worm](../../areas/zon/pworm.zon) | [Protection From Acid](../../src/magic/magic.c#L21936) (#105) | 3 | 833111 exit#0 → 42500; mobile #42500 at 42504. Purple worms and their acid: acid protection. |
| 458 | [Orog Encampment](../../areas/zon/orogs.zon) | [Warring Zeal](../../src/magic/magic.c#L25432) (#680) | 3 | Native hometown/tutorial arrival 45906; mobile #45808 at 45801. Orog encampment: Warring Zeal. Viper #45808 wanders north from reset room 45909 into public room 45801; it is not a sentinel. |
| 510 | [Hell, Avernus](../../areas/zon/hell_one_avernus.zon) | [Protection From Fire](../../src/classes/skills.c#L2301) (#96) | 3 | 45637 exit#0 → 51207; mobile #90701 at 51001. Avernus fire/devil encounters: fire protection. |
| 529 | [the Lost Temple of the North](../../areas/zon/multiclass_temple.zon) | [Sense Holiness](../../src/magic/magic.c#L7067) (#316) | 3 | 511126 exit#5 → 52901; mobile #31402 at 52909. Lost temple with ice golem/dragon encounters: sense holiness. |
| 530 | [Turolopolis Zoo](../../areas/zon/turolzoo.zon) | [Protection From Animals](../../src/magic/magic.c#L21864) (#383) | 3 | 7123 exit#3 → 53000; mobile #53011 at 53000. Zoo animals: protection from animals. |
| 531 | [Phantasmagoric Caverns](../../areas/zon/valdrak.zon) | [Detect Illusion](../../src/classes/sillusionist.c#L1797) (#414) | 3 | 831730 exit#1 → 53100; mobile #53117 at 53100. Phantasmagoric caverns: detect illusion. |
| 532 | [The Orcish Slave Camp](../../areas/zon/shortc.zon) | [Enhance Constitution](../../src/classes/psionics.c#L2650) (#178) | 3 | 10327 exit#1 → 53200; mobile #53200 at 53202. Orc slave camp: constitution for captives and guards. |
| 545 | [The Tunnels of Cyric the Destroyer](../../areas/zon/cyrictunnel.zon) | [Detect Evil](../../src/magic/magic.c#L9246) (#90) | 3 | 581796 exit#5 → 54500; mobile #54502 at 54509. Cyric’s tunnels: detect evil. |
| 678 | [The Undead Fog](../../areas/zon/shortb.zon) | [Sense Spirit](../../src/magic/smagic.c#L4244) (#211) | 3 | 569793 exit#1 → 67801; mobile #67807 at 67801. Undead fog and lost souls: sense spirit. |
| 690 | [The Mountain Village of Tentro](../../areas/zon/tentro2.zon) | [Fortitude](../../src/magic/magic.c#L6345) (#348) | 3 | 557287 exit#1 → 69080; mobile #69000 at 69000. Mountain village: hardy constitution. |
| 750 | [Dark Forest](../../areas/zon/dark_forest.zon) | [Scent Of The Bloodhound](../../src/magic/smagic.c#L2353) (#517) | 3 | 633650 exit#3 → 75171; mobile #75001 at 75001. Dark woodland trails: bloodhound scent. |
| 755 | [The Dark Stone Tower of the Northern Realms](../../areas/zon/teka2.zon) | [Energy Containment](../../src/classes/psionics.c#L2405) (#173) | 3 | 75264 exit#0 → 75546; mobile #75500 at 75500. Dark Stone Tower: energy containment. |
| 772 | [The Rice Fields](../../areas/zon/jademini.zon) | [Serendipity](../../src/magic/magic.c#L8284) (#352) | 3 | 642096 exit#0 → 77218; mobile #77205 at 77202. Rice harvest fields: serendipity. |
| 777 | [The Hall of the Ancients](../../areas/zon/hall.zon) | [Comprehend Languages](../../src/magic/magic.c#L17843) (#132) | 3 | 813247 exit#2 → 77700; mobile #77701 at 77707. Ancient halls: comprehension of old languages. |
| 806 | [Village of the Damned](../../areas/zon/yuan_ti2.zon) | [Protection From Evil](../../src/magic/magic.c#L10975) (#34) | 3 | 600250 exit#3 → 80600; mobile #80600 at 80605. Damned village: protection from evil. |
| 807 | [The Clawed Caverns](../../areas/zon/clwcvrn.zon) | [Enhance Dexterity](../../src/classes/psionics.c#L2564) (#176) | 3 | 819329 exit#1 → 80700; mobile #80739 at 80700. Clawed cavern creatures: enhanced dexterity. |
| 821 | [The Human Outpost](../../areas/zon/outpost.zon) | [Combat Mind](../../src/classes/psionics.c#L1094) (#163) | 3 | 527555 exit#1 → 82124; mobile #82102 at 82101. Military outpost: Combat Mind. |
| 822 | [Lylr-Meop](../../areas/zon/lylr.zon) | [Pulchritude](../../src/magic/magic.c#L8075) (#347) | 3 | 540876 exit#2 → 82200; mobile #82200 at 82201. Village encounters: charisma from Pulchritude. |
| 827 | [The Forgotten Forest](../../areas/zon/forgotten_forest.zon) | [Protection From Animals](../../src/magic/magic.c#L21864) (#383) | 3 | 516090 exit#1 → 82701; mobile #82705 at 82703. Forgotten Forest: animal protection; ZONE_SAFE does not block ordinary PvM attacks. |
| 879 | [The Stone Tomb of Kelek](../../areas/zon/kelek.zon) | [Sense Life](../../src/magic/magic.c#L12385) (#44) | 3 | 857219 exit#5 → 87950; mobile #87950 at 87962. Kelek’s tomb: sense life among the dead. |
| 882 | [The Temple of Blibdoolpoolp](../../areas/zon/kuotoa.zon) | [Water Breathing](../../src/classes/skills.c#L1571) (#85) | 3 | 4454 exit#1 → 88200; mobile #88201 at 88201. Kuo-toa temple: water breathing. |
| 885 | [The Minizones of the Underdark](../../areas/zon/udmini.zon) | [Lodestone Vision](../../src/magic/magic.c#L12484) (#617) | 3 | 54811 exit#4 → 88515; mobile #88500 at 88503. Underdark minizones and mineral caverns: Lodestone Vision. |
| 886 | [Morg's Place](../../areas/zon/morg.zon) | [Battletide](../../src/magic/magic.c#L16594) (#395) | 5 | 844836 exit#2 → 88600; mobile #88600 at 88600. Morg’s martial encounters: Battletide. |
| 900 | [The Fog Enshrouded Wood](../../areas/zon/foggy_woods.zon) | [Hawkvision](../../src/magic/smagic.c#L3281) (#204) | 3 | 579251 exit#3 → 90000; mobile #90021 at 90001. Foggy woodlands: Hawkvision. |
| 903 | [Tunnels of Payang](../../areas/zon/rtun.zon) | [Enhance Strength](../../src/classes/skills.c#L932) (#175) | 3 | 576997 exit#3 → 90380; mobile #90303 at 90301. Payang’s tunnel inhabitants: enhanced strength. |
| 908 | [Valinhaven](../../areas/zon/valinhav.zon) | [Sense Follower](../../src/magic/magic.c#L24629) (#279) | 3 | 798725 exit#3 → 90800; mobile #90813 at 90801. Valinhaven inhabitants: Sense Follower. |
| 914 | [Wutvr, Duris Newbie Outpost](../../areas/zon/wutvr.zon) | [Fortitude](../../src/magic/magic.c#L6345) (#348) | 3 | 91206 stream_of_life after guide conversation → 91401; mobile #91465 at 91428. Full Wutvr tutorial outpost: the same small constitution blessing, with an independent origin. |
| 930 | [Treasure Caves](../../areas/zon/dungeon.zon) | [Lodestone Vision](../../src/magic/magic.c#L12484) (#617) | 3 | 36004 exit#1 → 93115; mobile #93000 at 93000. Treasure caves: mineral detection. |
| 935 | [Wellvolen](../../areas/zon/wemic.zon) | [Wolfspeed](../../src/magic/smagic.c#L2683) (#193) | 3 | 572118 exit#1 → 93501; mobile #93503 at 93502. Wemic travelers of Wellvolen: Wolfspeed. |
| 939 | [Shadowclave](../../areas/zon/shadowcl.zon) | [Detect Good](../../src/magic/magic.c#L9283) (#91) | 3 | 545307 exit#2 → 93900; mobile #93900 at 93904. Shadowclave’s dark inhabitants: detect good. |
| 949 | [Llyrath Forest](../../areas/zon/llyrath.zon) | [Protection From Animals](../../src/magic/magic.c#L21864) (#383) | 3 | 26257 exit#2 → 94900; mobile #94901 at 94900. Llyrath forest creatures: protection from animals. |
| 953 | [Darkfall Forest](../../areas/zon/darkfall.zon) | [Sense Spirit](../../src/magic/smagic.c#L4244) (#211) | 3 | 515272 exit#1 → 95300; mobile #95300 at 95303. Darkfall forest: sense spirit. |
| 954 | [Troll Slave Compound](../../areas/zon/torture.zon) | [Enhance Constitution](../../src/classes/psionics.c#L2650) (#178) | 3 | 11529 exit#2 → 95400; mobile #95400 at 95401. Troll slave compound: constitution for endurance. |
| 958 | [Bugentolen](../../areas/zon/bugentol.zon) | [Enhance Dexterity](../../src/classes/psionics.c#L2564) (#176) | 3 | 589071 exit#3 → 95800; mobile #95800 at 95800. Bugentolen’s stalking inhabitants: enhanced dexterity. |
| 974 | [Arbre's Forest](../../areas/zon/sforest.zon) | [Sense Life](../../src/magic/magic.c#L12385) (#44) | 3 | 559312 exit#2 → 97400; mobile #97400 at 97401. Arbre’s forest: sense life. |
| 986 | [Village of Refugees](../../areas/zon/ruins.zon) | [Serendipity](../../src/magic/magic.c#L8284) (#352) | 3 | 627239 exit#2 → 98600; mobile #98600 at 98601. Refugee settlement: serendipity and hope. |
| 997 | [Lava Springs](../../areas/zon/lava.zon) | [Protection From Fire](../../src/classes/skills.c#L2301) (#96) | 3 | 565027 exit#0 → 99700; mobile #99700 at 99701. Lava springs: fire protection. |
| 1301 | [The Reliquary Nexus of Aggression](../../areas/zon/nexus_ic.zon) | [Divine Fury](../../src/magic/magic.c#L22267) (#310) | 3 | 511534 exit#1 → 130100; mobile #130110 at 130103. Reliquary Nexus of Aggression: Divine Fury. |
| 1302 | [The Reliquary Nexus of The Dead](../../areas/zon/nexus_uc.zon) | [Protection From Evil](../../src/magic/magic.c#L10975) (#34) | 3 | 577404 exit#2 → 130200; mobile #130200 at 130201. Reliquary Nexus of the Dead: protection from evil. |
| 1303 | [The Reliquary Nexus of the Corsairs](../../areas/zon/nexus_island.zon) | [Farsee](../../src/classes/skills.c#L1577) (#53) | 3 | 519153 exit#0 → 130301; mobile #130302 at 130308. Corsair island nexus: farsee. |
| 1304 | [The Reliquary Nexus of the Roper Den](../../areas/zon/nexus_roper.zon) | [Sense Spirit](../../src/magic/smagic.c#L4244) (#211) | 3 | 811645 exit#0 → 130400; mobile #130400 at 130401. Roper den: sense thinking creatures in the dark. |
| 1320 | [The Githyanki Fortress](../../areas/zon/githyanki_fortress.zon) | [Enhance Armor](../../src/classes/psionics.c#L2459) (#174) | 3 | 19798 exit#4 → 132000; mobile #132000 at 132008. Githyanki fortress: enhanced psionic armor. |
| 1350 | [Braddistock Mansion](../../areas/zon/brad.zon) | [Phantom Armor](../../src/classes/sillusionist.c#L131) (#400) | 3 | 132650 exit#0 → 135001; mobile #135014 at 135001. Independent Braddistock mansion: phantom armor, with separate origin/HP membership. |

Important gated witnesses: #180 uses switch #15282 in 15393 and switch #18031 in
18000; #304 uses switch #83195 in 83307 before portal #83141 in 83342; #510 uses
key #45532 reset in 45501 and switch #45503 in 45582. These openers are obtainable
before crossing their gates; no staff movement is used as entry evidence.

### Excluded active records

An exclusion does not delete content, prototypes, legacy items or roaming entries.
Disconnected destinations may be reconsidered when an enabled authored entrance
is added. Generic guessed teleport targets and retired surface links are not
entrance evidence. Existing catalog rows and the owner’s original 104 choices are
retained rather than silently dropped by the broader inventory screen.

| ID | Area | Exclusion reason |
|---:|---|---|
| -1 | [Limbo](../../areas/zon/limbo.zon) | Control/staff/afterlife record, not an ordinary collection area. |
| 0 | [Heaven](../../areas/zon/heavens.zon) | Control/staff/afterlife record, not an ordinary collection area. |
| 28 | [Verzanan](../../areas/zon/verz1.zon) | Retired or empty record: no local reset encounter and no authored player entrance. |
| 100 | [The Underworld Shafts](../../areas/zon/shafts.zon) | Underworld shaft connector; no independent reset encounter destination. |
| 110 | [The Adventurers Guildhalls](../../areas/zon/player_castles.zon) | Guild/private infrastructure, not a public collection destination. |
| 122 | [Northern Wilderness](../../areas/zon/northern_wilderness.zon) | Disconnected in the active world: no incoming enabled authored exit/placed portal reaches its encounter component; no native route to that destination was found. |
| 146 | [The Wildland Trails](../../areas/zon/wildland_trails.zon) | Disconnected in the active world: no incoming enabled authored exit/placed portal reaches its encounter component; no native route to that destination was found. |
| 150 | [Retired Misty Chasm prototypes](../../areas/zon/mist_chasm.zon) | Retired or empty record: no local reset encounter and no authored player entrance. |
| 195 | [The Crypts of Rays](../../areas/zon/graves.zon) | Retired or empty record: no local reset encounter and no authored player entrance. |
| 203 | [Nhavan Island](../../areas/zon/nhavan_island_one.zon) | Disconnected in the active world: no incoming enabled authored exit/placed portal reaches its encounter component; no native route to that destination was found. |
| 228 | [The Plains of Life](../../areas/zon/newbie2.zon) | Seven-room creation/racewar introduction; its normal encounters are level 1–2 and its guides are utility NPCs. The full tutorial outpost is classified separately. |
| 240 | [The Underdark](../../areas/zon/mobs_underdark.zon) | Roaming/patrol population staging infrastructure; its mobs serve other areas. #366 is also ZONE_SAFE. |
| 297 | [The Guildhall of Clan BloodLust](../../areas/zon/cbl_hall.zon) | Guild/private infrastructure, not a public collection destination. |
| 305 | [The Patrol Guard Headquarters](../../areas/zon/patrols.zon) | Roaming/patrol population staging infrastructure; its mobs serve other areas. #366 is also ZONE_SAFE. |
| 307 | [The Potion Treasure Vault](../../areas/zon/potions.zon) | Private object/unique storage vault, with no authored public entrance. |
| 314 | [the surface world](../../areas/zon/mobs_surf.zon) | Roaming/patrol population staging infrastructure; its mobs serve other areas. #366 is also ZONE_SAFE. |
| 366 | [The Wandering Fields](../../areas/zon/wander.zon) | Roaming/patrol population staging infrastructure; its mobs serve other areas. #366 is also ZONE_SAFE. |
| 380 | [Thetis's Realm](../../areas/zon/thetis.zon) | Excluded at the owner’s request in #706; preserve the recorded content decision. |
| 384 | [The Valoisian Castle](../../areas/zon/val.zon) | Excluded at the owner’s request in #706; preserve the recorded content decision. |
| 470 | [vehicles](../../areas/zon/vehicles.zon) | Vehicle/ship-room namespace and shipyard infrastructure; use the actual destination areas. |
| 480 | [Guildhalls](../../areas/zon/guildhalls.zon) | Guild/private infrastructure, not a public collection destination. |
| 514 | [Hell, Dis](../../areas/zon/hell_two_dis.zon) | Disconnected in the active world: no incoming enabled authored exit/placed portal reaches its encounter component; no native route to that destination was found. |
| 518 | [Hell, Minauros](../../areas/zon/hell_three_minauros.zon) | Disconnected in the active world: no incoming enabled authored exit/placed portal reaches its encounter component; no native route to that destination was found. |
| 522 | [Hell, Phlegethos](../../areas/zon/hell_four_phlegethos.zon) | Disconnected in the active world: no incoming enabled authored exit/placed portal reaches its encounter component; no native route to that destination was found. |
| 533 | [The Forest of Serenity](../../areas/zon/newfor.zon) | Disconnected in the active world: no incoming enabled authored exit/placed portal reaches its encounter component; no native route to that destination was found. |
| 536 | [The Great Realm of Duris](../../areas/zon/connectorzones.zon) | World connector infrastructure, rather than an independent adventure destination. |
| 546 | [Kvark's Great Connector](../../areas/zon/kvarkpass_connector.zon) | World connector infrastructure, rather than an independent adventure destination. |
| 600 | [The Adventurers Shipyards](../../areas/zon/ship.zon) | Vehicle/ship-room namespace and shipyard infrastructure; use the actual destination areas. |
| 651 | [Rabble](../../areas/zon/rabble.zon) | Utility shopkeeper rooms; no non-shop collection encounter. |
| 652 | [Adventurer's Vaults](../../areas/zon/lockers.zon) | Player storage/building/tradeskill infrastructure. |
| 672 | [The Unique's Vault](../../areas/zon/unique.zon) | Private object/unique storage vault, with no authored public entrance. |
| 673 | [Graendiae](../../areas/zon/sea.zon) | Disconnected in the active world: no incoming enabled authored exit/placed portal reaches its encounter component; no native route to that destination was found. |
| 679 | [CTF Tournament](../../areas/zon/arena.zon) | CTF event arena namespace, without repeatable ordinary collection encounters. |
| 773 | [Desolate Under Fire](../../areas/zon/desolateinv.zon) | Closed seasonal invasion record (ZONE_CLOSED); the ordinary Desolate area remains separate. |
| 856 | [An Ancient Bridge](../../areas/zon/ancientb.zon) | World connector infrastructure, rather than an independent adventure destination. |
| 870 | [Crakkaros' Liar](../../areas/zon/crakkaro.zon) | Keep the #706 exclusion: no enabled authored player entrance; do not restore routes as part of set work. |
| 904 | [Towering Glacier of Dayedenvale](../../areas/zon/glacier.zon) | Disconnected in the active world: no incoming enabled authored exit/placed portal reaches its encounter component; no native route to that destination was found. |
| 907 | [The River Styx](../../areas/zon/river_styx.zon) | Disconnected in the active world: no incoming enabled authored exit/placed portal reaches its encounter component; no native route to that destination was found. |
| 912 | [The Plane of Chaos](../../areas/zon/chaos_intro.zon) | Seven-room creation/racewar introduction; its normal encounters are level 1–2 and its guides are utility NPCs. The full tutorial outpost is classified separately. |
| 978 | [Buildings](../../areas/zon/buildings.zon) | Player storage/building/tradeskill infrastructure. |
| 998 | [Olympus](../../areas/zon/olympus.zon) | God/event/generated-space infrastructure, with no authored ordinary collection entrance. |
| 999 | [Interspace](../../areas/zon/interspa.zon) | God/event/generated-space infrastructure, with no authored ordinary collection entrance. |
| 1000 | [Randomness](../../areas/zon/random.zon) | God/event/generated-space infrastructure, with no authored ordinary collection entrance. |
| 1100 | [Tharnadia Rifts](../../areas/zon/tharnrifts.zon) | Global map/strategic geography record, not an independent adventure-area set. |
| 1200 | [The Depths of Duris](../../areas/zon/surfacekeeps.zon) | Global map/strategic geography record, not an independent adventure-area set. |
| 1340 | [The Tower of Darkness](../../areas/zon/lortower.zon) | Disconnected in the active world: no incoming enabled authored exit/placed portal reaches its encounter component; no native route to that destination was found. |
| 1351 | [The Altar of the Firesworn](../../areas/zon/firesworn_altar.zon) | Disconnected in the active world: no incoming enabled authored exit/placed portal reaches its encounter component; no native route to that destination was found. |
| 1352 | [The Lair of Tiamat](../../areas/zon/azhural.zon) | Disconnected in the active world: no incoming enabled authored exit/placed portal reaches its encounter component; no native route to that destination was found. |
| 1354 | [The Spires of the Elder Eternal Evil](../../areas/zon/eternal.zon) | Disconnected in the active world: no incoming enabled authored exit/placed portal reaches its encounter component; no native route to that destination was found. |
| 1380 | [The Ruins of Port Skythic](../../areas/zon/PortSkythic.zon) | Disconnected in the active world: no incoming enabled authored exit/placed portal reaches its encounter component; no native route to that destination was found. |
| 1420 | [The Para-Elemental Plane of Magma](../../areas/zon/magma.zon) | Disconnected in the active world: no incoming enabled authored exit/placed portal reaches its encounter component; no native route to that destination was found. |
| 1422 | [The Black Pearl](../../areas/zon/blackpearl.zon) | Keep the #706 exclusion: no enabled authored player entrance; do not restore routes as part of set work. |
| 4000 | [Tradeskills](../../areas/zon/tradeskills.zon) | Player storage/building/tradeskill infrastructure. |
| 5000 | [The Surface Realm of Duris](../../areas/zon/surface.zon) | Global map/strategic geography record, not an independent adventure-area set. |
| 7000 | [The Twisting Tunnels of the Durian Underdark](../../areas/zon/underdark.zon) | Global map/strategic geography record, not an independent adventure-area set. |
| 9999999 | [The End of the World](../../areas/zon/end.zon) | Control/staff/afterlife record, not an ordinary collection area. |

The four categories partition all 354 active records: 115 retained catalog rows,
104 original additions, 79 wider additions and 56 exclusions. This inventory count
includes control/map/staging records; it is distinct from the 298-row target set
catalog. No unresolved record is hidden behind an automatic “playable” assumption.

## Implementation handoff

Upstream PR #721 adds **#150 Retired Misty Chasm prototypes** as inert ownership
metadata. Its authored zone has no rooms or resets, so it is excluded from set
eligibility. The playable Chasm of the Misty Vale remains #3000 with its planned
assignment in the original roster; #150 does not change the 104 assignments
or their effect-home counts. See [mist_chasm.zon](../../areas/zon/mist_chasm.zon).
Its old header before `c79fde573` has the same visible title as #3000, so
unmarked historical Misty Vale items remain an HP-only legacy group. A current
#3000 title match alone cannot prove their origin or grant the new assignment;
new #3000 drops use their explicit origin marker.

The original roster exclusions, including Thetis's Realm (#380), Valoisian
Castle (#384), the Great Realm connector (#536), disconnected Crakkaros' Liar
(#870), and the disabled Black Pearl entrance (#1422), remain outside this plan.
Ceothia's three eras retain separate zone IDs and effect choices; resolving
legacy tags must not silently collapse them into one set. Barovia and Barovia
Continued deliberately receive the same effect, with separate zone identities.

Before installing the assignments, address #706's set-identity, mixed-set cleanup,
and report requirements, and keep set definitions separate from roaming-NPC
spawn selection. Verify Bloodstone Keep and another new zone from named drops
through the report and worn effects. Retain spell prerequisites, normal HP
behavior, and the original underpowered-first effect scope.

Sources checked: the current issue roster, the
[effect inventory](named-zone-set-effect-inventory.md),
[active area registry](../../areas/AREA), assigned zone/room/mobile files, and
[current set table](../../src/world/random.mob.c). Counts reconcile as
**42 initial assignments + 62 additional assignments = 104 unique roster zones**.
All 42 retained candidate IDs are still represented, and no proposed zone
already has a set definition in the inspected source. The 50 reused effects'
configured, initial-proposal, and additional-proposal home counts were reconciled
separately. This is a documentation update; gameplay validation belongs to
implementation.
