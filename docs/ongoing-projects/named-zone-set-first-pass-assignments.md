# Named zone sets: complete assignment plan and remaining work

Status: proposed assignments for all 104 roster zones; implementation pending.
Date: 2026-11-05.
Inspected `master`: `2d2a7d48dea91dbe773701790239db76f59806c2`.

Implementation entry point: [end-to-end plan](named-zone-set-implementation-plan.md),
including the seven-zone fixes, legacy-item policy, and verification gates.

## Scope and counts

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
| Total zones with a proposed effect | 104 |
| Zones still needing an effect choice | 0 |
| Assigned zones with known title/naming prerequisites | 7 |

**These are proposed assignments.** All 104 roster zones still lack set-table
rows in the inspected source. Seven also retain title/naming prerequisites,
listed below. The complete plan covers this roster; the issue's wider world
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
  remains **Shaman-only**, Virtue uses opposed alignment, and light/darkness
  effects retain their exclusions.
- Piece requirements and final spell power remain implementation choices.
  Preserve the ordinary matching-piece HP bonus and existing spell caps.

## The 42 proposed assignments

Sorted by zone number. Zone links point to the active zone definitions; effect
links point to the spell implementations used by the candidate inventory.

| Zone ID | Zone | Assigned effect (game ID) | Theme and existing restrictions |
|---:|---|---|---|
| 49 | [The Halfling Silver Mine](../../areas/zon/mining.zon) | [Lodestone Vision](../../src/magic/magic.c#L12484) (#617) | Mineral detection directly matches the silver mine and its miners. |
| 50 | [Labyrinth of No Return](../../areas/zon/labyrinth.zon) | [Detect Illusion](../../src/classes/sillusionist.c#L1797) (#414) | Seeing through deception fits a labyrinth and its confusing passages. |
| 69 | [The Caverns of the Worms](../../areas/zon/worms.zon) | [Slow Poison](../../src/magic/magic.c#L17814) (#130) | A poison-control utility theme fits underground worms and crawling vermin; the effect slows poison rather than removing it. |
| 108 | [The Haunted Woods](../../areas/zon/hwood.zon) | [Phantom Armor](../../src/classes/sillusionist.c#L131) (#400) | Phantom protection matches the haunted woodland theme. |
| 137 | [Tundra](../../areas/zon/tundra.zon) | [Fortitude](../../src/magic/magic.c#L6345) (#348) | Constitution fits the endurance demanded by the icy tundra. |
| 148 | [Bandit Camp](../../areas/zon/banditca.zon) | [Dexterity](../../src/magic/magic.c#L11563) (#73) | Nimble hands and footwork fit the bandit camp. |
| 164 | [Lord Krimeneha's Mansion](../../areas/zon/krimman.zon) | [Pulchritude](../../src/magic/magic.c#L8075) (#347) | A charm/appearance bonus suits a noble mansion and its alluring, sinister inhabitants. |
| 234 | [Mosswood](../../areas/zon/moss.zon) | [Protection From Gas](../../src/magic/magic.c#L21917) (#104) | Gas protection fits the area's mold and fungus creatures. |
| 326 | [The Fortress of Dreams](../../areas/zon/eth2.zon) | [Displacement](../../src/classes/psionics.c#L2206) (#169) | A shifting defensive image suits the fortress's ethereal and dreamlike setting. |
| 355 | [The Underground Lava Caves](../../areas/zon/lavcav.zon) | [Infravision](../../src/magic/magic.c#L22089) (#106) | Heat-oriented vision fits dark lava caves and their fire creatures. |
| 364 | [Arachdrathos - Drow City](../../areas/zon/arac-web.zon) | [Globe Of Darkness](../../src/magic/magic.c#L17667) (#302) | A carried darkness sphere suits an underground Drow city. Existing light/darkness exclusions apply. |
| 407 | [Home of the Divine](../../areas/zon/divhome.zon) | [Sense Holiness](../../src/magic/magic.c#L7067) (#316) | Sensing holiness directly matches the angels and divine guardians. |
| 444 | [Githzerai Stronghold](../../areas/zon/githzer.zon) | [Combat Mind](../../src/classes/psionics.c#L1094) (#163) | Mental discipline suits a Githzerai stronghold and its trained defenders. |
| 455 | [Celestial Plane](../../areas/zon/celestia.zon) | [Protection From Evil](../../src/magic/magic.c#L10975) (#34) | Protection from evil suits Celestia's guardians and celestial war grounds. |
| 490 | [The Desert City of Venan'Trut](../../areas/zon/desert.zon) | [Sense Follower](../../src/magic/magic.c#L24629) (#279) | Finding followers fits a busy desert city of travelers, merchants, and pack animals. |
| 575 | [the Mountain of Peril Peaks](../../areas/zon/nexus.zon) | [Adrenaline Control](../../src/classes/psionics.c#L412) (#157) | The dangerous mountain trails reward physical readiness: a Strength/Constitution theme. |
| 590 | [The Ravenloft Catacombs](../../areas/zon/ravenloft2.zon) | [Sense Life](../../src/magic/magic.c#L12385) (#44) | Sensing living creatures is useful thematic contrast in undead-filled catacombs. |
| 664 | [The Battlefield](../../areas/zon/battlefi.zon) | [Warring Zeal](../../src/magic/magic.c#L25432) (#680) | Battle focus and accuracy fit the soldiers and contested ground. |
| 708 | [Enclave of the Opal Phoenix](../../areas/zon/opalphoenix.zon) | [Holy Light](../../src/magic/magic.c#L17597) (#615) | A holy light theme matches the enclave's phoenix identity. Existing light/darkness exclusions apply. |
| 709 | [The Hall of Knighthood](../../areas/zon/knight.zon) | [Virtue](../../src/magic/magic.c#L6927) (#515) | Chivalric virtue fits the knights and their opposed vices. The existing opposed-alignment combat condition applies. |
| 740 | [Bloodstone Keep](../../areas/zon/bs.zon) | [Battletide](../../src/magic/magic.c#L16594) (#395) | A martial bonus for Bloodstone's fortified keep and its guards. |
| 760 | [The Sky City of Ultarium](../../areas/zon/cosmic.zon) | [Hawkvision](../../src/magic/smagic.c#L3281) (#204) | Long sight fits a high mountain sky city and its starwatcher setting. |
| 766 | [The Jade Empire](../../areas/zon/jade.zon) | [Enhance Dexterity](../../src/classes/psionics.c#L2564) (#176) | Controlled, precise movement suits the Jade Empire's martial tradition. |
| 780 | [Tribal Oasis](../../areas/zon/oasis.zon) | [Guardian Spirits](../../src/magic/smagic.c#L208) (#579) | Ancestral protection fits a tribal settlement with a mantis shaman. **Shaman wearers only**, as required by the existing spell. |
| 805 | [The Temple to Skrentherlog](../../areas/zon/yuan_ti.zon) | [Divine Fury](../../src/magic/magic.c#L22267) (#310) | Religious battle fury suits the Yuan-ti temple and its warriors. |
| 823 | [The Swamp Laboratory of Khul'Lor](../../areas/zon/lab.zon) | [Protection From Acid](../../src/magic/magic.c#L21936) (#105) | Acid protection is a fitting chemical-defense theme for a slimy swamp laboratory. |
| 831 | [Alatorin - the Forge City](../../areas/zon/alatorin.zon) | [Enhance Armor](../../src/classes/psionics.c#L2459) (#174) | Stronger armor suits a forge city and its metalworking identity. |
| 875 | [The 222nd Layer of the Abyss](../../areas/zon/juiblex.zon) | [Protection From Good](../../src/magic/magic.c#L11004) (#81) | Protection from good suits a demon- and slime-filled layer of the Abyss. |
| 877 | [Valley of the Snow Ogres](../../areas/zon/snogres.zon) | [Enhance Constitution](../../src/classes/psionics.c#L2650) (#178) | Hardiness fits the snow-ogre tribes and their cold mountain valley. |
| 878 | [The Church of the Eternal Dusk](../../areas/zon/church.zon) | [Detect Good](../../src/magic/magic.c#L9283) (#91) | An alignment sense gives the church a religious utility theme. |
| 890 | [The Village of New Hope](../../areas/zon/newhope.zon) | [Serendipity](../../src/magic/magic.c#L8284) (#352) | A small luck theme matches the settlement's promise of new hope. |
| 910 | [The Realm of Barovia](../../areas/zon/barovia.zon) | [Lifelust](../../src/magic/magic.c#L7776) (#321) | A life-hungry combat blessing fits Barovia's undead-haunted setting. |
| 933 | [Centaur Villages](../../areas/zon/centaur_zone.zon) | [Wolfspeed](../../src/magic/smagic.c#L2683) (#193) | A larger movement pool suits centaur travelers and the area's wolves. |
| 943 | [The Behemoth Herders](../../areas/zon/herders.zon) | [Scent Of The Bloodhound](../../src/magic/smagic.c#L2353) (#517) | Tracking by scent fits an area centered on herders, riders, and behemoths. |
| 989 | [Ruined Temple of Tezcatlipoca](../../areas/zon/tezcat.zon) | [Detect Evil](../../src/magic/magic.c#L9246) (#90) | Sensing evil suits the exploration of a ruined dark temple. |
| 1310 | [The BrimStone Forge](../../areas/zon/brimeforge.zon) | [Mage Flame](../../src/magic/magic.c#L17626) (#297) | A small magical flame fits the BrimStone Forge's fire-and-smithing identity. Existing light/darkness exclusions apply. |
| 1382 | [Mitashi - Capital City of the Jade Empire](../../areas/zon/mitashi.zon) | [Comprehend Languages](../../src/magic/magic.c#L17843) (#132) | Language comprehension fits an imperial capital populated by multiple clans, merchants, and visitors. |
| 1385 | [The Savannah of Broken Trusts](../../areas/zon/savannah.zon) | [Protection From Animals](../../src/magic/magic.c#L21864) (#383) | Protection from wild beasts fits the savannah's leopards, panthers, and other animals. |
| 1398 | [The Para-Elemental Plane of Smoke](../../areas/zon/smoke.zon) | [Vapor Strike](../../src/classes/ethermancer.c#L1134) (#467) | A vapor-themed accuracy bonus fits a plane populated by smoke creatures. |
| 1424 | [The Royal Mausoleum of Castle IceCrag](../../areas/zon/Voluntown.zon) | [Sense Spirit](../../src/magic/smagic.c#L4244) (#211) | Spirit detection matches a royal mausoleum and its dead inhabitants. |
| 3000 | [The Chasm of the Misty Vale](../../areas/zon/thechasmofthemistyvale.zon) | [Vapor Armor](../../src/classes/ethermancer.c#L104) (#452) | Mist-shaped armor fits the Misty Vale and its forested chasm approach. |
| 4020 | [The Arcaneum of L'srillizzin](../../areas/zon/library.zon) | [Energy Containment](../../src/classes/psionics.c#L2405) (#173) | Containing magical energy suits the Arcaneum and its elemental golems. |

## The 62 additional assignments

The home-count column is the combined configured-plus-initial-plan count at
the **start** of this reuse pass. It is not a running count after each row.
Zone links identify the area; effect links follow the source inventory.

| Zone ID | Zone | Reused effect (game ID) | Homes before reuse pass | Theme and existing restrictions |
|---:|---|---|---:|---|
| 13 | [Braddistock Mansion](../../areas/zon/braddistock.zon) | [Phantom Armor](../../src/classes/sillusionist.c#L131) (#400) | 1 | The mansion's resident spirit and ratman mages fit a phantom-defense theme. Resolve the existing Braddistock title collision before implementation. |
| 17 | [The Docks of Quietus Quay](../../areas/zon/quietus.zon) | [Dexterity](../../src/magic/magic.c#L11563) (#73) | 1 | Sure hands and footing fit work around the docks, warehouses, and steep harbor approaches. |
| 22 | [The Seacaves](../../areas/zon/seacaves.zon) | [Water Breathing](../../src/classes/skills.c#L1571) (#85) | 4 | Water breathing directly matches the sea caves, coastal pools, and water elementals. This stronger thematic fit takes priority over its existing four homes. |
| 42 | [Ixxillikor](../../areas/zon/ixxillikor.zon) | [Combat Mind](../../src/classes/psionics.c#L1094) (#163) | 1 | Mental discipline fits a neogi settlement with an enslaved workforce and umber-hulk guards. |
| 44 | [The Underworld](../../areas/zon/underworld.zon) | [Globe Of Darkness](../../src/magic/magic.c#L17667) (#302) | 1 | A carried darkness sphere fits the deep underground river and cavern settlement. Preserve light exclusions and resolve the existing Underworld title collision. |
| 55 | [The Tharnadian Ruin](../../areas/zon/tharnadian_ruin.zon) | [Holy Light](../../src/magic/magic.c#L17597) (#615) | 1 | A guiding holy light fits a ruined city populated by restless spirits. Preserve the existing light/darkness exclusions. |
| 62 | [The Cimmerian Nomad Encampment](../../areas/zon/nomads.zon) | [Wolfspeed](../../src/magic/smagic.c#L2683) (#193) | 1 | A larger movement pool suits the nomads' wagons and travel across the plains. |
| 71 | [The Ruins of Turolopolis](../../areas/zon/willem.zon) | [Detect Good](../../src/magic/magic.c#L9283) (#91) | 1 | The holy shaman provides a concrete religious theme for sensing good among the ruined streets. |
| 76 | [Bastine Castle](../../areas/zon/bastine.zon) | [Pulchritude](../../src/magic/magic.c#L8075) (#347) | 1 | A royal court headed by a king and queen suits a charisma/appearance bonus. |
| 78 | [Vargan II](../../areas/zon/v2.zon) | [Infravision](../../src/magic/magic.c#L22089) (#106) | 1 | Heat-oriented vision fits the ancient dark passages and their underground inhabitants. |
| 132 | [The Twin Towers](../../areas/zon/ttowers.zon) | [Displacement](../../src/classes/psionics.c#L2206) (#169) | 1 | A magical defensive image fits the towers' magic shop, mirrors, and magically reinforced passages. |
| 135 | [Twin Towers Forest](../../areas/zon/twin_towers_forest.zon) | [Farsee](../../src/classes/skills.c#L1577) (#53) | 1 | Long sight suits scouting the forest paths inhabited by wolves and pixies. |
| 163 | [A Dark and Twisted Wood](../../areas/zon/twstwd.zon) | [Slow Poison](../../src/magic/magic.c#L17814) (#130) | 1 | Slowing poison directly fits the poisonous ivy and dangerous vegetation. |
| 204 | [Neverwind Valley](../../areas/zon/pyramid.zon) | [Sense Life](../../src/magic/magic.c#L12385) (#44) | 1 | Sensing living creatures contrasts with the valley's skeletons, zombies, spectres, and wraiths. Its plain title still needs the naming-eligibility fix. |
| 209 | [Mountain Tracts of the Untamed](../../areas/zon/mountaintracks.zon) | [Adrenaline Control](../../src/classes/psionics.c#L412) (#157) | 1 | Physical readiness fits the steep mountain trails, caves, and untamed predators. |
| 236 | [Malch'Hor Ganl the Goblin City](../../areas/zon/malch.zon) | [Agility](../../src/classes/skills.c#L2053) (#584) | 1 | Agility fits goblin thieves moving through narrow tunnels and a crowded underground city. |
| 281 | [Verspin](../../areas/zon/verspin.zon) | [Serendipity](../../src/magic/magic.c#L8284) (#352) | 1 | Luck fits a trading town with gem shops, merchants, and a trade master. |
| 344 | [Defense of Longhollow](../../areas/zon/long.zon) | [Battletide](../../src/magic/magic.c#L16594) (#395) | 1 | A martial accuracy/damage bonus fits the fighting templars, wounded knight, and opposing guards. |
| 352 | [The City of Newhaven](../../areas/zon/newhaven.zon) | [Detect Evil](../../src/magic/magic.c#L9246) (#90) | 1 | Detecting evil fits a city with knights and their corrupted zombie, vampire, wraith, and lich counterparts. |
| 358 | [Abandoned Elven Homestead](../../areas/zon/elvish.zon) | [Sense Spirit](../../src/magic/smagic.c#L4244) (#211) | 1 | Spirit detection directly fits the spirit of an Elven protector in the abandoned homestead. |
| 404 | [Golden Hall of the Crown](../../areas/zon/gold_hal.zon) | [Virtue](../../src/magic/magic.c#L6927) (#515) | 1 | Virtue fits the fortress's knight trainees and their master teacher. Preserve the existing opposed-alignment combat condition. |
| 422 | [Tribal Forest](../../areas/zon/tribal.zon) | [Guardian Spirits](../../src/magic/smagic.c#L208) (#579) | 1 | Ancestral protection fits the tribal shaman and young shaman apprentice. **Shaman wearers only**, as required by the existing spell. |
| 429 | [Drustl's Yerdonia Enslaved](../../areas/zon/raxthan.zon) | [Protection From Good](../../src/magic/magic.c#L11004) (#81) | 1 | An evil-sided ward fits the slave master, witch doctor, assassins, and oppressive Raxian guards. |
| 430 | [Prison of Fort Boyard](../../areas/zon/prisonb.zon) | [Protection From Acid](../../src/magic/magic.c#L21936) (#105) | 1 | Acid protection fits the prison's black dragon and its broader collection of dangerous dragons. |
| 431 | [The Ship Yards](../../areas/zon/shipy.zon) | [Enhance Dexterity](../../src/classes/psionics.c#L2564) (#176) | 1 | Precise hands and footwork fit shipyard work, dockside gear, and harbor guards. |
| 435 | [Temple of the Earth](../../areas/zon/earth.zon) | [Fortitude](../../src/magic/magic.c#L6345) (#348) | 1 | Constitution and resilience fit the mountain temple, duergar guardians, and earth golems. |
| 437 | [Lost City of Tikitzopl](../../areas/zon/tikit.zon) | [Slow Poison](../../src/magic/magic.c#L17814) (#130) | 1 | Slowing poison directly fits the Snake Pit and the explicitly poisonous fangs of its inhabitants. |
| 550 | [The City of Winterhaven](../../areas/zon/wh.zon) | [Comprehend Languages](../../src/magic/magic.c#L17843) (#132) | 1 | Understanding languages fits a major city whose authored rooms explicitly handle ambassadors to Alatorin. |
| 570 | [The Trakkia Mountains](../../areas/zon/trakkia.zon) | [Enhance Constitution](../../src/classes/psionics.c#L2650) (#178) | 1 | Constitution fits the rugged foothills and mountain tribes. |
| 588 | [The Realm of Barovia Continued](../../areas/zon/barovia2.zon) | [Lifelust](../../src/magic/magic.c#L7776) (#321) | 1 | Lifelust fits the bloodthirsty werewolves, witches, and Vistani of Barovia's continuation, echoing the main area's planned theme without sharing set identity. |
| 660 | [Ashrumite Village](../../areas/zon/ashrumite.zon) | [Detect Illusion](../../src/classes/sillusionist.c#L1797) (#414) | 1 | Seeing through illusions directly fits the village's illusionist guildmaster and magical guilds. |
| 666 | [City of Torrhan](../../areas/zon/torrhan.zon) | [Warring Zeal](../../src/magic/magic.c#L25432) (#680) | 1 | Battle accuracy fits the city's tower guards, elite guards, and captain of the guards. |
| 712 | [The Scorched Valley](../../areas/zon/scorchvalley.zon) | [Protection From Gas](../../src/magic/magic.c#L21917) (#104) | 1 | Gas protection fits the opening description's choking fumes from burning vegetation and bodies. |
| 752 | [Northern Lakes and Settlements](../../areas/zon/nlakes.zon) | [Protection From Cold](../../src/classes/skills.c#L2308) (#97) | 2 | Cold protection directly matches the icy footpaths and northern settlements. The environmental fit takes priority over its existing two homes. |
| 775 | [The Mountain Valley of Dawndale](../../areas/zon/airshipgrave.zon) | [Hawkvision](../../src/magic/smagic.c#L3281) (#204) | 1 | Long sight suits scouts and guards moving along high mountain trails around an elven settlement. |
| 784 | [The Twin Keeps of Devastated Tharnadia](../../areas/zon/caertannad.zon) | [Divine Fury](../../src/magic/magic.c#L22267) (#310) | 1 | Religious battle fury fits the rival fortified keeps, smashed altars, and streets dedicated to the duergar god Grunthorigard. |
| 808 | [Ceothia](../../areas/zon/ceothia.zon) | [Enhance Agility](../../src/classes/skills.c#L944) (#177) | 1 | Agility fits present-day Ceothia's shadow thieves and moonstone thieves. Resolve the shared Ceothia title before implementation. |
| 811 | [Ceothia](../../areas/zon/ceopast.zon) | [Protection From Animals](../../src/magic/magic.c#L21864) (#383) | 1 | Protection from animals directly fits the wolf packs in Ceothia's densely forested past. Resolve the shared Ceothia title before implementation. |
| 814 | [Ceothia](../../areas/zon/ceofutur.zon) | [Vapor Strike](../../src/classes/ethermancer.c#L1134) (#467) | 1 | A vapor-themed accuracy bonus fits future Ceothia's smoky, scorched camps and battle-scarred landscape. Resolve the shared Ceothia title before implementation. |
| 820 | [Jindon the Deathwood Forest](../../areas/zon/jin.zon) | [Detect Illusion](../../src/classes/sillusionist.c#L1797) (#414) | 1 | Seeing through tricks fits a carnival with performers, magical merchandise, and conjuring entertainments. |
| 825 | [Myrabolus](../../areas/zon/mira.zon) | [Sense Holiness](../../src/magic/magic.c#L7067) (#316) | 1 | Sensing holiness directly fits the holy knights, celestial white dragon, and Home of the Holy. |
| 828 | [The Motte and Bailey of Duke Delwyn](../../areas/zon/delwyn.zon) | [Enhance Armor](../../src/classes/psionics.c#L2459) (#174) | 1 | Improved armor fits a fortified motte and bailey with a master bladesmith and a guard garrison. |
| 883 | [The Charcoal Palace](../../areas/zon/firep.zon) | [Energy Containment](../../src/classes/psionics.c#L2405) (#173) | 1 | Containing elemental energy fits a palace surrounded by molten rock, sulfur, and fire minions. |
| 888 | [Menden-on-the-Deep](../../areas/zon/menden.zon) | [Mage Flame](../../src/magic/magic.c#L17626) (#297) | 1 | A small magical light fits the village magus and the explicitly described fire-magic experiments. Preserve light/darkness exclusions. |
| 889 | [Fishermans Wharf](../../areas/zon/fishermans_wharf.zon) | [Sense Follower](../../src/magic/magic.c#L24629) (#279) | 1 | Finding followers fits keeping track of companions around a working wharf, dirty piers, and coastal paths. |
| 920 | [The Ruins of Undermountain](../../areas/zon/undermountain.zon) | [Displacement](../../src/classes/psionics.c#L2206) (#169) | 1 | A shifting defense fits a sprawling dungeon of hidden rooms, shadowbeasts, and dangerous corridors. |
| 940 | [The Maze of Undead Army](../../areas/zon/maze_are.zon) | [Protection From Evil](../../src/magic/magic.c#L10975) (#34) | 1 | Protection from evil fits the old graveyard, soulless guardians, lich priest, and undead army. |
| 947 | [The Deep Ravine of Passage](../../areas/zon/minopass.zon) | [Farsee](../../src/classes/skills.c#L1577) (#53) | 1 | Long sight directly suits watching across a deep ravine and its rocky mountain passes. |
| 950 | [Mistywood](../../areas/zon/mistywood.zon) | [Vapor Armor](../../src/classes/ethermancer.c#L104) (#452) | 1 | Mist-shaped armor directly matches the misty woodland and river setting. |
| 968 | [Dirk'nspire Stronghold](../../areas/zon/dirkn.zon) | [Lodestone Vision](../../src/magic/magic.c#L12484) (#617) | 1 | Mineral detection fits the Deep Dwarves and the stronghold's underground rock tunnels. |
| 969 | [Troll Caves](../../areas/zon/troll_caves.zon) | [Enhance Strength](../../src/classes/skills.c#L932) (#175) | 1 | Strength fits the troll inhabitants and their cavern stronghold. |
| 970 | [IceCrag Castle](../../areas/zon/icecrag.zon) | [Enhance Constitution](../../src/classes/psionics.c#L2650) (#178) | 1 | Hardiness fits a cold castle staffed by patrol guards, an Ice Priest, and siege defenders. |
| 979 | [The Minizones of the Surface](../../areas/zon/surfacemini.zon) | [Serendipity](../../src/magic/magic.c#L8284) (#352) | 1 | A luck bonus suits a collection of small adventures and unusual encounters, including Gorblaat's Cave. |
| 985 | [The Bandit Canyons](../../areas/zon/bandit.zon) | [Enhance Dexterity](../../src/classes/psionics.c#L2564) (#176) | 1 | Dexterous movement fits the bandits, canyon ambushes, and scrub-covered campsites. |
| 990 | [Neverwinter Woods](../../areas/zon/moria.zon) | [Scent Of The Bloodhound](../../src/magic/smagic.c#L2353) (#517) | 1 | Scent-based tracking fits a woodland expedition among the elves. Its plain title still needs the naming-eligibility fix. |
| 994 | [Varathorn Keep](../../areas/zon/kastle.zon) | [Protection From Evil](../../src/magic/magic.c#L10975) (#34) | 1 | Protection from evil fits ruined halls occupied by zombie guards, skeletal knights, and a vampire guardian. |
| 995 | [Cloud Giant Kingdom](../../areas/zon/cldgt.zon) | [Enhance Strength](../../src/classes/skills.c#L932) (#175) | 1 | Strength directly matches the cloud giant warriors and heroes. |
| 1300 | [Vecna's Tomb](../../areas/zon/vecna.zon) | [Sense Spirit](../../src/magic/smagic.c#L4244) (#211) | 1 | Spirit detection fits Vecna's tomb, its shadows, death knights, and barrow guardians. |
| 1312 | [Grumbar's Domain](../../areas/zon/earthp.zon) | [Lodestone Vision](../../src/magic/magic.c#L12484) (#617) | 1 | Mineral detection directly fits Grumbar's earth realm and its huge geode dragon. |
| 1316 | [The Tempest Court](../../areas/zon/airp.zon) | [Protection From Lightning](../../src/classes/skills.c#L2347) (#98) | 1 | Lightning protection directly matches the Heart of the Storm and the Tempest Court. |
| 1389 | [The Ancient Halls of Ironstar](../../areas/zon/lornecro.zon) | [Sense Life](../../src/magic/magic.c#L12385) (#44) | 1 | Sensing living creatures contrasts with the Ironstar halls' guardian wights, skeletal defenders, and apprentice necromancer. |
| 1390 | [Plane of Fire, Brass](../../areas/zon/brass.zon) | [Protection From Fire](../../src/classes/skills.c#L2301) (#96) | 1 | Fire protection directly matches the City of Brass, efreeti, fire giants, and Imix Avenue. |

## Effect homes after both passes

Only the 50 effects used by the reuse pass are shown. Current homes are
recounted from loaded zones in the existing set table. Proposed homes become
current homes when the assignments are implemented.

| Effect (game ID) | Current loaded-zone homes | Initial proposed homes | Additional proposed homes | Combined homes after plan |
|---|---:|---:|---:|---:|
| [Adrenaline Control](../../src/classes/psionics.c#L412) (#157) | 0 | 1 | 1 | 2 |
| [Agility](../../src/classes/skills.c#L2053) (#584) | 1 | 0 | 1 | 2 |
| [Battletide](../../src/magic/magic.c#L16594) (#395) | 0 | 1 | 1 | 2 |
| [Combat Mind](../../src/classes/psionics.c#L1094) (#163) | 0 | 1 | 1 | 2 |
| [Comprehend Languages](../../src/magic/magic.c#L17843) (#132) | 0 | 1 | 1 | 2 |
| [Detect Evil](../../src/magic/magic.c#L9246) (#90) | 0 | 1 | 1 | 2 |
| [Detect Good](../../src/magic/magic.c#L9283) (#91) | 0 | 1 | 1 | 2 |
| [Detect Illusion](../../src/classes/sillusionist.c#L1797) (#414) | 0 | 1 | 2 | 3 |
| [Dexterity](../../src/magic/magic.c#L11563) (#73) | 0 | 1 | 1 | 2 |
| [Displacement](../../src/classes/psionics.c#L2206) (#169) | 0 | 1 | 2 | 3 |
| [Divine Fury](../../src/magic/magic.c#L22267) (#310) | 0 | 1 | 1 | 2 |
| [Energy Containment](../../src/classes/psionics.c#L2405) (#173) | 0 | 1 | 1 | 2 |
| [Enhance Agility](../../src/classes/skills.c#L944) (#177) | 1 | 0 | 1 | 2 |
| [Enhance Armor](../../src/classes/psionics.c#L2459) (#174) | 0 | 1 | 1 | 2 |
| [Enhance Constitution](../../src/classes/psionics.c#L2650) (#178) | 0 | 1 | 2 | 3 |
| [Enhance Dexterity](../../src/classes/psionics.c#L2564) (#176) | 0 | 1 | 2 | 3 |
| [Enhance Strength](../../src/classes/skills.c#L932) (#175) | 1 | 0 | 2 | 3 |
| [Farsee](../../src/classes/skills.c#L1577) (#53) | 1 | 0 | 2 | 3 |
| [Fortitude](../../src/magic/magic.c#L6345) (#348) | 0 | 1 | 1 | 2 |
| [Globe Of Darkness](../../src/magic/magic.c#L17667) (#302) | 0 | 1 | 1 | 2 |
| [Guardian Spirits](../../src/magic/smagic.c#L208) (#579) | 0 | 1 | 1 | 2 |
| [Hawkvision](../../src/magic/smagic.c#L3281) (#204) | 0 | 1 | 1 | 2 |
| [Holy Light](../../src/magic/magic.c#L17597) (#615) | 0 | 1 | 1 | 2 |
| [Infravision](../../src/magic/magic.c#L22089) (#106) | 0 | 1 | 1 | 2 |
| [Lifelust](../../src/magic/magic.c#L7776) (#321) | 0 | 1 | 1 | 2 |
| [Lodestone Vision](../../src/magic/magic.c#L12484) (#617) | 0 | 1 | 2 | 3 |
| [Mage Flame](../../src/magic/magic.c#L17626) (#297) | 0 | 1 | 1 | 2 |
| [Phantom Armor](../../src/classes/sillusionist.c#L131) (#400) | 0 | 1 | 1 | 2 |
| [Protection From Acid](../../src/magic/magic.c#L21936) (#105) | 0 | 1 | 1 | 2 |
| [Protection From Animals](../../src/magic/magic.c#L21864) (#383) | 0 | 1 | 1 | 2 |
| [Protection From Evil](../../src/magic/magic.c#L10975) (#34) | 0 | 1 | 2 | 3 |
| [Protection From Fire](../../src/classes/skills.c#L2301) (#96) | 1 | 0 | 1 | 2 |
| [Protection From Gas](../../src/magic/magic.c#L21917) (#104) | 0 | 1 | 1 | 2 |
| [Protection From Good](../../src/magic/magic.c#L11004) (#81) | 0 | 1 | 1 | 2 |
| [Protection From Lightning](../../src/classes/skills.c#L2347) (#98) | 1 | 0 | 1 | 2 |
| [Pulchritude](../../src/magic/magic.c#L8075) (#347) | 0 | 1 | 1 | 2 |
| [Scent Of The Bloodhound](../../src/magic/smagic.c#L2353) (#517) | 0 | 1 | 1 | 2 |
| [Sense Follower](../../src/magic/magic.c#L24629) (#279) | 0 | 1 | 1 | 2 |
| [Sense Holiness](../../src/magic/magic.c#L7067) (#316) | 0 | 1 | 1 | 2 |
| [Sense Life](../../src/magic/magic.c#L12385) (#44) | 0 | 1 | 2 | 3 |
| [Sense Spirit](../../src/magic/smagic.c#L4244) (#211) | 0 | 1 | 2 | 3 |
| [Serendipity](../../src/magic/magic.c#L8284) (#352) | 0 | 1 | 2 | 3 |
| [Slow Poison](../../src/magic/magic.c#L17814) (#130) | 0 | 1 | 2 | 3 |
| [Vapor Armor](../../src/classes/ethermancer.c#L104) (#452) | 0 | 1 | 1 | 2 |
| [Vapor Strike](../../src/classes/ethermancer.c#L1134) (#467) | 0 | 1 | 1 | 2 |
| [Virtue](../../src/magic/magic.c#L6927) (#515) | 0 | 1 | 1 | 2 |
| [Warring Zeal](../../src/magic/magic.c#L25432) (#680) | 0 | 1 | 1 | 2 |
| [Wolfspeed](../../src/magic/smagic.c#L2683) (#193) | 0 | 1 | 1 | 2 |
| [Protection From Cold](../../src/classes/skills.c#L2308) (#97) | 2 | 0 | 1 | 3 |
| [Water Breathing](../../src/classes/skills.c#L1571) (#85) | 4 | 0 | 1 | 5 |

## Remaining work

**No roster zone is left without a proposed effect.** These seven assignments
still need the already documented title/naming work before their zone tags
can function unambiguously or be generated as intended.

| Zone ID | Zone | Proposed effect | Outstanding prerequisite |
|---:|---|---|---|
| 13 | [Braddistock Mansion](../../areas/zon/braddistock.zon) | [Phantom Armor](../../src/classes/sillusionist.c#L131) (#400) | Resolve the legacy title collision with Braddistock Mansion #1350. |
| 44 | [The Underworld](../../areas/zon/underworld.zon) | [Globe Of Darkness](../../src/magic/magic.c#L17667) (#302) | Resolve the legacy title collision with The Underworld #300. |
| 204 | [Neverwind Valley](../../areas/zon/pyramid.zon) | [Sense Life](../../src/magic/magic.c#L12385) (#44) | Plain title: enable zone-named drops as part of the naming-eligibility work. |
| 808 | [Ceothia](../../areas/zon/ceothia.zon) | [Enhance Agility](../../src/classes/skills.c#L944) (#177) | Shares the Ceothia title with #811 and #814; establish distinct or explicitly shared set identity. |
| 811 | [Ceothia](../../areas/zon/ceopast.zon) | [Protection From Animals](../../src/magic/magic.c#L21864) (#383) | Shares the Ceothia title with #808 and #814; establish distinct or explicitly shared set identity. |
| 814 | [Ceothia](../../areas/zon/ceofutur.zon) | [Vapor Strike](../../src/classes/ethermancer.c#L1134) (#467) | Shares the Ceothia title with #808 and #811; establish distinct or explicitly shared set identity. |
| 990 | [Neverwinter Woods](../../areas/zon/moria.zon) | [Scent Of The Bloodhound](../../src/magic/smagic.c#L2353) (#517) | Plain title: enable zone-named drops as part of the naming-eligibility work. |

## Implementation handoff

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
