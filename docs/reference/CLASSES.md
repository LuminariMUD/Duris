# Player classes

This is the starting point for PC (player character) class documentation. It
connects the player help, creation rules, progression rules, configuration, and
implementation. The availability lists below describe the checked-in configuration
with `CREATION_ALL_CLASSES=FALSE` and `CREATION_ALL_RACES=FALSE`; they do not
describe a live server's settings or prove that every ability works in play.

For a tunable design budget based on the ordinary roster, see the
[class point system](CLASS-POINTS.md). It defines capability prices, initial
reference scorecards, and a process for evaluating balance changes and new
classes; its point estimates are distinct from these implemented rules.

- [Existing resources](#existing-resources)
- [Class catalogue](#class-catalogue)
- [Creation and alignment](#creation-and-alignment)
- [Specializations](#specializations)
- [Learning, spell circles, and resources](#learning-spell-circles-and-resources)
- [Multiclassing](#multiclassing)
- [Stats, equipment, and identity](#stats-equipment-and-identity)
- [Unavailable commands and temporary forms](#unavailable-commands-and-temporary-forms)
- [Implementation map](#implementation-map)
- [Verification and maintenance](#verification-and-maintenance)

## Existing resources

For players, start with `help classes`, `help <class>`, `help <class> skills`,
`help skill_<class>`, `help specialization`, and `help multiclass`. For example,
`help warrior`, `help warrior skills`, and `help skill_warrior` refer to the
Warrior description and its two skillset topic names. Use `specialize` to list
your own choices and `specialize list` to list specialization/race definitions.
`skills`, `spells`, and `innate` describe the current character's abilities.

| Resource | What it supplies |
| --- | --- |
| [Classes](../../help/duris_help_parsed.hlp#L4288), [Specialization](../../help/duris_help_parsed.hlp#L22409), [Multiclass](../../help/duris_help_parsed.hlp#L15397), [Class Guides](../../help/duris_help_parsed.hlp#L4274) | Current overview, navigation, specialization, and multiclass help. |
| [Parsed help](../../help/duris_help_parsed.hlp) | Main descriptions and skill/spell entries for all 30 class IDs, plus specialization, multiclass, and individual ability topics. Each class has direct links below. |
| [Help index](../../lib/information/help_index) | The other import source: class entries, `SKILL_<CLASS>` entries, commands, spells, skills, and specialization topics. |
| [Help system](../content/HELP_SYSTEM.md), [cache operation](../operations/help-cache.md), [help style](../content/HELP_STYLE_GUIDE.md) | Source precedence, database/flat-file serving, dynamic sections, refresh, and editing conventions. |
| [Classes and races operator guide](../content/classes_and_races.txt) | How to enable/disable creation choices and change the race/class matrix. |
| [Creation switches](../../lib/creation_availability.cfg), [environment example](../../.env.example) | Checked-in creation policy and the broader testing overrides. |
| [Boot-loaded class-menu text](../../lib/creation/classtable) | The fallback text is loaded at boot; current creation builds its class menu from code and configuration. |
| [Command attributes](../lib/information/command_attributes.txt) | The stats used by individual commands/abilities; these attributes are also appended to in-game help. |
| [Character mechanics plan](../ongoing-projects/class-anchor.md) | Proposed mechanical traceability and deeper lifecycle qualification. It remains an implementation plan, not a completed verification report. |
| [Chaos mode](CHAOS_MODE.md), [Chaos kit catalogue](CHAOS_KIT_CATALOG.md), [standard starter kits](LEGACY_STARTER_KITS.md) | Alternate creation rewards, equipment, and starter-kit behavior. Receiving a Chaos or staff grant does not establish an ordinary acquisition route. |
| [Codebase map](CODEBASE.md), [experience trophies](EXPERIENCE_TROPHIES.md), [progression telemetry](../telemetry/PROGRESSION.md) | Shared gameplay ownership, XP observations, and progression records. |
| [Player saves](../persistence/PLAYER_SAVE_PIPELINE.md), [critical commands](../persistence/CRITICAL_COMMAND_PIPELINE.md) | Saved character state, transaction APIs, and their durability boundaries. |

Imported help contains complete authored lists. The importer assigns category
`0` to both maintained sources. In database-backed mode,
[wikihelp.c](../../src/cmd/wikihelp.c) appends races, innates, specializations,
skills, or spells to pages explicitly assigned a dynamic category. Those
additions use code tables; they are not a second check of creation policy.
For example, a race help
page can list Dragoon from `class_table` while the creation switch disables it.
The importer gives parsed-help titles precedence over matching help-index
titles. Database-backed servers serve the imported catalog, so changing a file
alone does not publish help. See the help-system resource above for the exact
pipeline and the separate flat-file path.

## Class catalogue

The server defines **30 class IDs** in
[defines.h](../../src/core/defines.h), with names and specialization slots in
[common.c](../../src/core/common.c). An ID being defined does not mean it is
offered during ordinary creation. `CLASS_*` values are bit flags; the ID below
is the corresponding 1-based table index (`flag2idx`), not the flag value.

The short roles summarize the existing class help. Exact grants and conditions
come from the implementation and character state, rather than the description's
flavor text. Specializations below are **defined names**, not a promise that
every race can select them. The [availability section](#creation-and-alignment)
identifies the classes without a normal creation route.

| ID | Class description / skill help | Role | Defined specializations |
| --- | --- | --- | --- |
| 1 | [Warrior](../../help/duris_help_parsed.hlp#L23887) / [skills](../../help/duris_help_parsed.hlp#L23920) | Front-line weapon combat, defense, and protection. | [Swordsman](../../help/duris_help_parsed.hlp#L24233); [Guardian](../../help/duris_help_parsed.hlp#L11224); [Swashbuckler](../../help/duris_help_parsed.hlp#L3306) |
| 2 | [Ranger](../../help/duris_help_parsed.hlp#L18509) / [skills](../../help/duris_help_parsed.hlp#L18542) | Nature magic, tracking, and two-weapon combat. | [Blademaster](../../help/duris_help_parsed.hlp#L2913); [Huntsman](../../help/duris_help_parsed.hlp#L12355); [Marshall](../../help/duris_help_parsed.hlp#L14306) |
| 3 | [Psionicist](../../help/duris_help_parsed.hlp#L17749) / [skills](../../help/duris_help_parsed.hlp#L17780) | Mental powers and psionic offense/control. | [Pyrokinetic](../../help/duris_help_parsed.hlp#L18035); [Enslaver](../../help/duris_help_parsed.hlp#L7746); [Psycheporter](../../help/duris_help_parsed.hlp#L17814) |
| 4 | [Paladin](../../help/duris_help_parsed.hlp#L16440) / [skills](../../help/duris_help_parsed.hlp#L16479) | Holy martial combat, protection, and group auras. | [Crusader](../../help/duris_help_parsed.hlp#L5327); [Cavalier](../../help/duris_help_parsed.hlp#L3773) |
| 5 | [Anti-Paladin](../../help/duris_help_parsed.hlp#L1152) / [skills](../../help/duris_help_parsed.hlp#L24172) | Evil martial combat, dark magic, and group support. | [Dark Knight](../../help/duris_help_parsed.hlp#L5604); [Demonic Rider](../../help/duris_help_parsed.hlp#L5855); [Violator](../../help/duris_help_parsed.hlp#L24259) |
| 6 | [Cleric](../../help/duris_help_parsed.hlp#L4322) / [skills](../../help/duris_help_parsed.hlp#L4355) | Healing and protective divine magic. | [Zealot](../../help/duris_help_parsed.hlp#L24294); [Healer](../../help/duris_help_parsed.hlp#L11737); [Holyman](../../help/duris_help_parsed.hlp#L12162) |
| 7 | [Monk](../../help/duris_help_parsed.hlp#L15056) / [skills](../../help/duris_help_parsed.hlp#L15087) | Unarmed martial arts and disciplined physical combat. | [Red Dragon](../../help/duris_help_parsed.hlp#L18911); [Elaphidist](../../help/duris_help_parsed.hlp#L7282) |
| 8 | [Druid](../../help/duris_help_parsed.hlp#L6870) / [skills](../../help/duris_help_parsed.hlp#L6904) | Nature magic and forest/storm abilities. | [Forest Druid](../../help/duris_help_parsed.hlp#L9134); [Storm Druid](../../help/duris_help_parsed.hlp#L24329) |
| 9 | [Shaman](../../help/duris_help_parsed.hlp#L20248) / [skills](../../help/duris_help_parsed.hlp#L20280) | Elemental, spirit, and animal magic. | [Elementalist](../../help/duris_help_parsed.hlp#L7420); [Spiritualist](../../help/duris_help_parsed.hlp#L24362); [Animalist](../../help/duris_help_parsed.hlp#L1075) |
| 10 | [Sorcerer](../../help/duris_help_parsed.hlp#L22200) / [skills](../../help/duris_help_parsed.hlp#L22232) | Offensive arcane spellcasting. | [Wildmage](../../help/duris_help_parsed.hlp#L24393); [Wizard](../../help/duris_help_parsed.hlp#L24417); [Shadowmage](../../help/duris_help_parsed.hlp#L20180) |
| 11 | [Necromancer](../../help/duris_help_parsed.hlp#L15689) / [skills](../../help/duris_help_parsed.hlp#L15720) | Death magic and undead servants. | [Diabolis](../../help/duris_help_parsed.hlp#L6109); [Necrolyte](../../help/duris_help_parsed.hlp#L15664); [Reaper](../../help/duris_help_parsed.hlp#L18713) |
| 12 | [Conjurer](../../help/duris_help_parsed.hlp#L4784) / [skills](../../help/duris_help_parsed.hlp#L4817) | Conjuration, enchantment, and elemental magic. | [Air Magus](../../help/duris_help_parsed.hlp#L814); [Water Magus](../../help/duris_help_parsed.hlp#L24443); [Fire Magus](../../help/duris_help_parsed.hlp#L8579); [Earth Magus](../../help/duris_help_parsed.hlp#L7130) |
| 13 | [Rogue](../../help/duris_help_parsed.hlp#L19404) / [skills](../../help/duris_help_parsed.hlp#L19459) | Stealth, deception, and opportunistic attacks. | [Assassin](../../help/duris_help_parsed.hlp#L24471); [Thief](../../help/duris_help_parsed.hlp#L24513); [Shadow Archer](../../help/duris_help_parsed.hlp#L24558); slot 3 is reserved |
| 14 | [Assassin](../../help/duris_help_parsed.hlp#L1616) / [skills](../../help/duris_help_parsed.hlp#L24068) | Standalone stealth/assassination class. | No named menu slots; ordinary Assassin is a Rogue specialization |
| 15 | [Mercenary](../../help/duris_help_parsed.hlp#L14578) / [skills](../../help/duris_help_parsed.hlp#L14611) | Martial/rogue hybrid and privateer. | [Brigand](../../help/duris_help_parsed.hlp#L3412); [Bounty Hunter](../../help/duris_help_parsed.hlp#L3249) |
| 16 | [Bard](../../help/duris_help_parsed.hlp#L2373) / [skills](../../help/duris_help_parsed.hlp#L2405) | Music, group support, and mixed martial/magical skills. | [Disharmonist](../../help/duris_help_parsed.hlp#L6305); [Scoundrel](../../help/duris_help_parsed.hlp#L19796); [Minstrel](../../help/duris_help_parsed.hlp#L14846) |
| 17 | [Thief](../../help/duris_help_parsed.hlp#L23947) / [skills](../../help/duris_help_parsed.hlp#L23978) | Standalone theft/stealth class. | No named menu slots; ordinary Thief is a Rogue specialization |
| 18 | [Warlock](../../help/duris_help_parsed.hlp#L24006) / [skills](../../help/duris_help_parsed.hlp#L24032) | Negative-energy spellcasting class. | None defined |
| 19 | [MindFlayer](../../help/duris_help_parsed.hlp#L23825) / [skills](../../help/duris_help_parsed.hlp#L23852) | Illithid-associated psionic class. | None defined |
| 20 | [Alchemist](../../help/duris_help_parsed.hlp#L860) / [skills](../../help/duris_help_parsed.hlp#L889) | Potion mixing and thrown concoctions. | [Battle-Forger](../../help/duris_help_parsed.hlp#L2536); [Blacksmith](../../help/duris_help_parsed.hlp#L2891) |
| 21 | [Berserker](../../help/duris_help_parsed.hlp#L2739) / [skills](../../help/duris_help_parsed.hlp#L2769) | Rage-driven melee combat. | [Mauler](../../help/duris_help_parsed.hlp#L14476); [Ragelord](../../help/duris_help_parsed.hlp#L18273) |
| 22 | [Reaver](../../help/duris_help_parsed.hlp#L18738) / [skills](../../help/duris_help_parsed.hlp#L18770) | Martial combat with elemental magic. | [Ice Reaver](../../help/duris_help_parsed.hlp#L24587); [Flame Reaver](../../help/duris_help_parsed.hlp#L8794); [Shock Reaver](../../help/duris_help_parsed.hlp#L3043); [Earth Reaver](../../help/duris_help_parsed.hlp#L24615) |
| 23 | [Illusionist](../../help/duris_help_parsed.hlp#L12525) / [skills](../../help/duris_help_parsed.hlp#L12556) | Illusions, deception, and shadow magic. | [Magician](../../help/duris_help_parsed.hlp#L14101); [Dark Dreamer](../../help/duris_help_parsed.hlp#L5580) |
| 24 | [Blighter](../../help/duris_help_parsed.hlp#L23754) / [skills](../../help/duris_help_parsed.hlp#L23788) | Corrupted nature magic and destructive weather. | [Storm Bringer](../../help/duris_help_parsed.hlp#L24643); [Scourge](../../help/duris_help_parsed.hlp#L24667); [Ruiner](../../help/duris_help_parsed.hlp#L24692) |
| 25 | [Dreadlord](../../help/duris_help_parsed.hlp#L6681) / [skills](../../help/duris_help_parsed.hlp#L6713) | Undead martial/spellcasting class. | [Deathlord](../../help/duris_help_parsed.hlp#L5748); [Shadowlord](../../help/duris_help_parsed.hlp#L24715) |
| 26 | [Ethermancer](../../help/duris_help_parsed.hlp#L8123) / [skills](../../help/duris_help_parsed.hlp#L8156) | Ice/wind magic, dispelling, and magical disruption. | [Tempest Magus](../../help/duris_help_parsed.hlp#L24738); [Frost Magus](../../help/duris_help_parsed.hlp#L9363); [Star Magus](../../help/duris_help_parsed.hlp#L5058) |
| 27 | [Avenger](../../help/duris_help_parsed.hlp#L2019) / [skills](../../help/duris_help_parsed.hlp#L2053) | Celestial martial/divine class. | [Lightbringer](../../help/duris_help_parsed.hlp#L13635); [Inquisitor](../../help/duris_help_parsed.hlp#L24775) |
| 28 | [Theurgist](../../help/duris_help_parsed.hlp#L23685) / [skills](../../help/duris_help_parsed.hlp#L23715) | Celestial invocations and divine/arcane magic. | [Medium](../../help/duris_help_parsed.hlp#L24797); [Templar](../../help/duris_help_parsed.hlp#L24822); [Thaumaturge](../../help/duris_help_parsed.hlp#L24847) |
| 29 | [Summoner](../../help/duris_help_parsed.hlp#L23617) / [skills](../../help/duris_help_parsed.hlp#L23649) | Bound creatures, planar magic, and barriers. | [Controller](../../help/duris_help_parsed.hlp#L24872); [Mentalist](../../help/duris_help_parsed.hlp#L24894); [Naturalist](../../help/duris_help_parsed.hlp#L24919) |
| 30 | [Dragoon](../../help/duris_help_parsed.hlp#L23548) / [skills](../../help/duris_help_parsed.hlp#L23582) | Mounted draconic martial combat and invocations. | [Dragon Hunter](../../help/duris_help_parsed.hlp#L24944); [Dragon Priest](../../help/duris_help_parsed.hlp#L24972); [Dragon Lancer](../../help/duris_help_parsed.hlp#L24997) |

## Creation and alignment

Normal creation requires an offered/enabled race, an enabled class, and a legal
race/class cell, followed by the transport's alignment and account-admission
checks. The authorities are `playable_races` and `class_table` in
[constant.c](../../src/core/constant.c),
[creation_availability_config.c](../../src/account/creation_availability_config.c),
[nanny.c](../../src/account/nanny.c), and
[ws_handlers.c](../../src/net/ws_handlers.c).

The 21 normal races are Human, Barbarian, Grey Elf, Mountain Dwarf, Halfling,
Gnome, Centaur, Githzerai, Firbolg, Drow, Duergar, Ogre, Troll, Orc, Githyanki,
Goblin, Kobold, Drider, Thri-kreen, Minotaur, and Tiefling. The lists below
transpose their current `class_table` cells. Duergar means Duergar Dwarf.

Alignment codes: **A** = any (`2`), **G** = good (`1`), **N** = neutral (`0`),
**E** = evil (`-1`), **GN** = good/neutral (`3`), **NE** = neutral/evil (`4`).
Code `5` forbids the combination. Alignment is distinct from racewar side.

| Class | Legal normal-roster race cells, grouped by alignment |
| --- | --- |
| Warrior | A: Human, Barbarian, Grey Elf, Mountain Dwarf, Halfling, Gnome, Centaur, Githzerai, Firbolg, Thri-kreen, Minotaur, Tiefling. E: Drow, Duergar, Ogre, Troll, Orc, Githyanki, Goblin, Kobold, Drider. |
| Ranger | G: Human, Grey Elf, Halfling, Centaur, Githzerai, Tiefling. |
| Psionicist | G: Githzerai. E: Githyanki. |
| Paladin | G: Human, Githzerai, Tiefling. |
| Anti-Paladin | E: Orc, Githyanki, Tiefling. |
| Cleric | A: Human, Grey Elf, Mountain Dwarf, Halfling, Gnome, Githzerai, Tiefling. E: Drow, Duergar, Orc, Githyanki, Goblin, Kobold. |
| Monk | G: Human. E: Orc. A: Tiefling. |
| Druid | N: Human, Grey Elf, Halfling, Centaur, Githzerai. |
| Shaman | A: Human, Barbarian, Grey Elf, Halfling, Gnome, Centaur, Minotaur, Tiefling. N: Firbolg. E: Drow, Ogre, Troll, Orc, Goblin, Kobold. |
| Sorcerer | A: Human, Grey Elf, Halfling, Gnome, Githzerai, Minotaur, Tiefling. E: Drow, Orc, Githyanki, Goblin, Kobold, Drider. |
| Necromancer | E: Human, Gnome, Githzerai, Drow, Orc, Githyanki, Goblin, Kobold, Drider. |
| Conjurer | A: Human, Grey Elf, Halfling, Gnome, Githzerai, Tiefling. E: Drow, Orc, Githyanki, Goblin, Kobold. |
| Rogue | NE: Human. N: Barbarian, Grey Elf, Mountain Dwarf, Halfling, Tiefling. E: Drow, Duergar, Troll, Orc, Githyanki, Goblin. |
| Mercenary | A: Human, Barbarian, Grey Elf, Mountain Dwarf, Halfling, Gnome, Minotaur, Tiefling. E: Drow, Duergar, Troll, Orc, Goblin, Kobold. |
| Bard | G: Human, Grey Elf, Halfling, Gnome, Githzerai. E: Drow, Orc, Githyanki, Goblin, Kobold. A: Tiefling. |
| Berserker | N: Human, Barbarian, Mountain Dwarf. E: Duergar, Troll, Orc. A: Minotaur. |
| Reaver | E: Drow, Duergar, Orc, Githyanki, Goblin, Drider, Tiefling. |
| Illusionist | A: Human, Grey Elf, Halfling, Gnome, Githzerai, Tiefling. E: Drow, Orc, Githyanki, Goblin, Kobold. |
| Blighter | E: Drow, Orc, Githyanki, Goblin, Drider. |
| Ethermancer | N: Human, Grey Elf, Halfling, Githzerai, Drow, Orc, Githyanki, Goblin, Kobold. A: Tiefling. |
| Summoner | A: Human, Grey Elf, Halfling, Gnome, Githzerai, Tiefling. E: Drow, Orc, Githyanki, Goblin, Kobold. |
| Dragoon | **Disabled by creation policy.** If enabled: A: Human, Grey Elf, Githzerai, Tiefling. NE: Drow, Orc, Githyanki. |

Assassin, Thief, Warlock, MindFlayer, Alchemist, Dreadlord, Avenger, and Theurgist
have **no legal cell among those 21 races**. Their `enabled=true` switches do
not create a legal cell. Assassin and Thief normally mean Rogue
specializations, rather than their retained standalone class IDs. Restricted
races can have different cells; inspect `restricted_races`, `class_table`, and
`restricted_class_rows` before making a claim about them.

The checked-in [availability file](../../lib/creation_availability.cfg) disables
only Dragoon among the 30 class switches. Missing switches default to enabled;
the file is read at boot. `CREATION_ALL_CLASSES=TRUE` bypasses class switches
and changes forbidden creation cells to code `2`, while retaining already
legal cells' alignment codes. It also bypasses specialization race filtering.
It does not by itself remove teacher, learning, level, or equipment requirements.
`CREATION_ALL_RACES=TRUE` exposes the separate restricted-race roster, still
subject to its race switches, and enables the replacement creation rows for
restricted races whose normal matrix row is empty. Neither switch changes
`class_table` for its other consumers. Both overrides are `FALSE` in the
committed environment example.

**Telnet and WebSocket alignment differ.** Telnet applies fixed G/N/E cells or
offers the choices in A/GN/NE cells. WebSocket advertises those codes but derives
good/evil alignment from race faction (or a good/evil choice for neutral-faction
races), then enforces only fixed G/E requirements. It does not assign neutral
alignment for N cells or enforce GN/NE choices in the same way. For example,
Human Necromancer is a legal evil matrix cell, but WebSocket assigns Human good
alignment and rejects that selection. Treat the table as matrix eligibility,
not proof that both clients can complete every listed combination.

## Specializations

`specialize <name>` selects a specialization at level **30** or higher. The
current [handler](../../src/classes/specializations.c) requires a PC with no
secondary class, no existing specialization, an expired `time_unspecced` timer,
a suitable teacher in the room, and an allowed race/class/spec combination.
An ordinary teacher is a matching-class NPC with `ACT_SPEC_TEACHER`; a trusted
PC with the required consent link is another accepted path. Success sets
`player.spec` and calls `update_skills`.

`allowed_race_specs` is independent of the creation matrix. For example, the
Warrior menu defines three paths, but Thri-kreen has only Swordsman in its
allowed specialization rows. A defined specialization is therefore insufficient
to establish that a particular character can take it. Rogue's ordinary allowed
rows select Assassin or Thief; Shadow Archer is defined but has no allowed
race row. Slot 3 contains the literal placeholder `Not Used`, which is not a
documented playable path. The all-classes override bypasses the race/spec
predicate, including for classes that normally lack eligible races.

Dragoons use other classes' specialization teachers: Ranger/Mercenary for
Dragon Hunter, Shaman/Druid for Dragon Priest, and Paladin/Anti-Paladin for
Dragon Lancer. The handler checks the selected path against the teacher as well
as the race/spec predicate. Opening Dragoon creation does not remove this check.

The standalone Assassin and Thief IDs have empty specialization-name rows.
When directly created with the all-classes override, `do_start_impl` in
[actwiz.c](../../src/cmd/actwiz.c) assigns their retained legacy spec slots
(`SPEC_ASSMASTER` / `SPEC_CUTPURSE`) before initializing skills. These are
different from selecting Assassin or Thief on a Rogue.

To remove a specialization, the assigned `unspec_altar` objects (VNUMs 2203
and 12016) accept `pray altar`. The
[altar handler](../../src/specs/specs.object.c) calls `unspecialize`, which
requires an existing specialization and **10 epic points**. The successful in-memory purchase callback clears the spec, updates skills,
and forgets prepared spells. It runs before the API returns; normal character
saves persist the balance and character state. The current function does not
set a new `time_unspecced` cooldown.
Assignments identify handlers, not guaranteed world availability of an altar.

## Learning, spell circles, and resources

[skills.c](../../src/classes/skills.c) is the authority for ordinary ability
registration: `SKILL_CREATE` / `SPELL_CREATE` identify the ability and spell
callback; `SKILL_ADD`, `SPELL_ADD`, and their specialization variants supply
class/spec requirements. `rlevel` means a **character level for a skill** and a
**spell circle for a spell**. A registration is not a promise that the character
has been taught, practiced, prepared, or can currently use the ability.
[guild.c](../../src/guild/guild.c) owns learning/practice and skill updates;
[memorize.c](../../src/classes/memorize.c) owns spell eligibility, slots, and
preparation. [epic_skills.c](../../src/classes/epic_skills.c) adds epic-skill
eligibility, teachers, prerequisites, costs, and in-memory purchase completion.

`get_max_circle` uses `1 + (level - 1) / 5`, bounded to the supported circles.
Circles 1 through 12 therefore open at levels **1, 6, 11, 16, 21, 26, 31, 36,
41, 46, 51, and 56**. A class/spec must still grant the individual spell at an
accessible circle; a prepared spell restored from a save must also pass current
eligibility.

Preparation/resource modes are selected by the class/race predicates in
[utils.h](../../src/core/utils.h) and the handlers in `memorize.c`:

- Spellbook classes are Sorcerer, Conjurer, Necromancer, Illusionist, Bard,
  Summoner, Reaver, and Theurgist. Shaman also belongs to the memorizing group.
- Cleric, Paladin, Anti-Paladin, and Avenger belong to the praying group.
- Druid, Ranger, and Dragoon use commune; Blighter uses deforest.
- Psionicist and MindFlayer, and Illithid/Planetbound Illithid races, use mana
  under the relevant primary/secondary-class predicates. Ethermancer and Harpy
  use tupor. Undead, celestial, and other form predicates can select slot paths.
- Dragoon's slots are mount-dependent: mounting starts commune, and its
  commune path checks the mount. Its use of the `undead_spell_slots` field does
  not make the character undead. See [mount.c](../../src/classes/mount.c) and
  the [Dragoon spellcasting contract](../../tests/async/test_dragoon_spellcasting.py).

For multiclass characters, primary class and race can select the preparation
path; the two classes are not interchangeable. Inspect those predicates rather
than assuming all casters use mana or all spells use a spellbook.

The maximum supported level is not the currently unlocked level.
[frag_cap.cfg](../../lib/frag_cap.cfg) sets the current repository policy:
floor 25, reset level 30, maximum 56, a three-day unlock timer, and a Hardcore
allowance of two levels beyond the side cap, clamped to 56. The database's
`level_cap` row holds live unlock state; qualifying frags and timers advance it.
See [the cap implementation](../../src/combat/frag_cap_config.c),
[the codebase progression reference](CODEBASE.md#frag-based-level-caps), and
[limits.c](../../src/world/limits.c). The client-free SQL fallback uses the
configured floor; it does not reproduce a live season's progression.

## Multiclassing

Only **Human and Orc PCs** can use the ordinary multiclass command. `multiclass`
lists possible secondary classes; selection happens through `multiclass <class>`
in a room with `multiclass_proc` (assigned VNUMs 17 and 52904). The checked-in
[properties](../../lib/duris.properties) require **level 50** and **0 epic
points**. The epic requirement is a balance threshold, not a deduction.
Without these properties, the listing handler defaults to level 41, while the
room defaults to level 50 and 250 epics; use configured values rather than
treating either fallback as the current policy.

The following are the ordered candidate pairs from `allowed_secondary_classes`
in [constant.c](../../src/core/constant.c). The final target must also have a
non-forbidden cell for the character's race in the original `class_table`;
`can_char_multi_to_class` in [utility.c](../../src/core/utility.c) does not use
the creation switches or all-classes override. The helper checks that cell's
legality, not its alignment code against the character's current alignment.

| Primary class | Candidate secondary classes before race filtering |
| --- | --- |
| Warrior | Mercenary; Cleric |
| Ranger | Warrior; Druid; Rogue; Psionicist |
| Paladin | Warrior |
| Anti-Paladin | Warrior |
| Cleric | Druid; Bard; Warrior; Shaman |
| Shaman | Conjurer; Druid; Cleric; Blighter |
| Sorcerer | Conjurer |
| Conjurer | Sorcerer; Shaman; Bard |
| Rogue | Bard; Mercenary |
| Mercenary | Rogue; Warrior |
| Bard | Sorcerer; Rogue; Illusionist; Conjurer |
| Reaver | Sorcerer; Rogue; Psionicist |
| Ethermancer | Sorcerer; Shaman |
| Summoner | Sorcerer; Shaman |

All other primary-class rows have no candidates. Reversing a pair need not be
legal: Paladin can add Warrior, while Warrior cannot add Paladin. The much
larger `multiclass_names` table supplies display names and is not eligibility.
For example, Ranger's Psionicist candidate is filtered out for Human because
Human's Psionicist cell is forbidden.

Multiclassing is a restart of progression. The
[room handler](../../src/specs/specs.room.c) calls `do_start` before assigning
the secondary class, resetting level to 1 and XP to 1. It preserves played time,
clears the specialization, restores the character, forgets prepared spells,
refunds epic skills, and clears XP trophies. `do_start_impl` also resets ordinary
learned skills and prestige and puts a guilded character on parole. The room
does not reject an existing specialization; it clears it. This is distinct
from `specialize`, which rejects an existing secondary class.

For skill metadata, `SKILL_DATA_ALL` keeps primary-only requirements, adds **5**
to secondary-only `rlevel`, and takes the lower primary/adjusted secondary
requirement for a shared grant. Thus secondary-only ordinary skills require
five extra character levels. Its current cap multipliers are **100% primary /
95% secondary**. Spell circles have a separate rule in `get_spell_circle`:
use the primary spell's circle when present; otherwise a secondary-only spell
costs **one extra circle**, provided the result fits within the supported
circles. Do not apply the metadata helper's `+5` as the casting-circle rule.

The usual multiclass preparation factors are **1.75**. Epic rewards available
only through the secondary class apply additional **2x epic-point / 3x coin**
cost factors to the normal purchase cost. Those factors do not apply to a
reward already allowed by the primary class. The relevant resource path and
purchase prerequisites still apply.

Removing a secondary class uses the assigned altar route. Object VNUM 44165 is assigned `unmulti_altar`, which
accepts `pray altar`; `unmulti` in [actinf.c](../../src/cmd/actinf.c) requires
**100 epic points**. Its successful in-memory purchase callback clears secondary class
and spec, forgets prepared spells, and updates skills. It does not restore the
pre-multiclass level, XP, or skill snapshot. An assigned altar is not evidence
that a player has acquired access to it in a deployed world.

## Stats, equipment, and identity

Class is only one input to a character's performance. Race stat factors,
equipment, level, affects, specialization, skill learning, and runtime properties
also matter. Consult the class's help for its intended role and
[command attributes](../lib/information/command_attributes.txt) for the actual
stats used by an ability, rather than assuming a single universal best stat.

- `calculate_hitpoints2` in [affects.c](../../src/magic/affects.c) combines level,
  constitution, racial constitution, class modifiers, and other bonuses. The
  `hitpoints.class.<ClassName>` properties are inputs to this formula, not a
  direct multiplier of final displayed HP. For multiclass PCs it takes the
  larger class modifier. Illithids have a separate branch. Dragoon currently has
  no explicit HP property and uses the loader's `1.0` fallback.
- Innates are assigned in [innates.c](../../src/classes/innates.c) by race,
  class, specialization, and unlock level. An active innate has a handler;
  a passive can have a null handler and an effect consumed elsewhere. For
  example, Guardian's Bulwark is granted at level 41 and the
  [combat consumer](../../src/combat/fight.c) applies it while wearing a shield.
  A name on the list is not a guarantee that its conditions are met.
- Item restrictions live in [handler.c](../../src/world/handler.c) and wear/use
  commands in [actobj.c](../../src/cmd/actobj.c), using class/race allow or deny
  masks and body/equipment rules. Some checks deliberately use only the primary
  class. The creation switches do not remove these restrictions.
- `GET_CLASS` includes secondary class; `GET_PRIME_CLASS` does not. `GET_SPEC`
  checks primary class plus spec slot. True race, effective race for an innate,
  and displayed/disguised race also differ. The definitions in
  [utility.c](../../src/core/utility.c), [utils.h](../../src/core/utils.h), and
  `innates.c` determine which identity each feature uses.

## Unavailable commands and temporary forms

Ascend and descend are unavailable to player characters. The current denial
paths do not consume the inputs described by their unreachable bodies. Temporary
forms remain separate from class identity.

| Route | Current source behavior |
| --- | --- |
| Paladin to Avenger / celestial ascension | `do_ascend` in [actoth.c](../../src/cmd/actoth.c) returns immediately for PCs. Its Paladin/Avenger bodies and `ascend_theurgist` are not an ordinary player unlock. |
| Necromancer to Lich / descension | `do_descend` checks Necromancer and level 50, then explicitly returns disabled before transforming. The retained helper also rejects PCs. |
| Dragoon draconic apotheosis | Registered as a circle-12 spell in `skills.c`. The [spell body](../../src/magic/magic.c) requires Dragoon and its linked/ridden mount, rejects combat, consumes the mount, and applies a temporary dragon race affect. This is a form change, not another class. |
| Revenant crown | [Object handlers](../../src/specs/specs.object.c) and assignments bind object 22070 to `revenant_helm`. This changes race temporarily; it does not acquire a class. |

Shapechange, corpseform, phantasmal/wraith forms, world race changes, and staff
setters need their own eligibility and reversal checks. The
[character mechanics plan](../ongoing-projects/class-anchor.md) inventories these
routes and their unresolved lifecycle proof. In particular, `AFFTYPE_NOSAVE`
does not prove that every changed identity field safely reverses on death,
quit/relog, or restart. This reference makes no such persistence claim.

## Implementation map

These shared owners are the starting points for exact mechanics and new work:

| Concern | Current resources |
| --- | --- |
| IDs, names, slots, race/class matrix, ordered multiclass choices | [defines.h](../../src/core/defines.h), [common.c](../../src/core/common.c), [constant.c](../../src/core/constant.c) |
| Creation, both clients, and switches | [creation_availability_config.c](../../src/account/creation_availability_config.c), [nanny.c](../../src/account/nanny.c), [ws_handlers.c](../../src/net/ws_handlers.c) |
| Ability registration, learning, specialization, innates | [skills.c](../../src/classes/skills.c), [guild.c](../../src/guild/guild.c), [specializations.c](../../src/classes/specializations.c), [innates.c](../../src/classes/innates.c) |
| Casting, preparation, mounts, epic purchases | [sparser.c](../../src/net/sparser.c), [memorize.c](../../src/classes/memorize.c), [mount.c](../../src/classes/mount.c), [epic_skills.c](../../src/classes/epic_skills.c) |
| Class-specific handlers | [paladins.c](../../src/classes/paladins.c), [reavers.c](../../src/classes/reavers.c), [avengers.c](../../src/classes/avengers.c), [dreadlord.c](../../src/classes/dreadlord.c), [shaman.c](../../src/classes/shaman.c), [ethermancer.c](../../src/classes/ethermancer.c), [necromancy.c](../../src/classes/necromancy.c), [rogues.c](../../src/classes/rogues.c), [psionics.c](../../src/classes/psionics.c), [bard.c](../../src/classes/bard.c), [sillusionist.c](../../src/classes/sillusionist.c), [salchemist.c](../../src/classes/salchemist.c) |
| Shared spells, physical abilities, effects, combat, and equipment | [magic/](../../src/magic/), [new_skills.c](../../src/classes/new_skills.c), [combat/](../../src/combat/), [affects.c](../../src/magic/affects.c), [handler.c](../../src/world/handler.c) |
| World route binding and handlers | [specs.assign.c](../../src/specs/specs.assign.c), [specs.room.c](../../src/specs/specs.room.c), [specs.mobile.c](../../src/specs/specs.mobile.c), [specs.object.c](../../src/specs/specs.object.c), [specs.shabo.c](../../src/specs/specs.shabo.c), [loaded areas](../../areas/AREA) |
| Class state capture and reconstruction | [player_snapshot_capture.c](../../src/player/player_snapshot_capture.c), [player_load_materialize.c](../../src/player/player_load_materialize.c) |
| Class-dependent tuning | [duris.properties](../../lib/duris.properties), [frag_cap.cfg](../../lib/frag_cap.cfg), [property loading](../../src/world/properties.c), [racewar stat modifiers](../../src/combat/racewar_stat_mods.c) |

Not every class has a dedicated implementation file. Follow the ability's
registration into its spell handler, command, passive consumer, or world proc.
The registration's class/spec slot and the consumer's identity checks together
determine behavior.

## Verification and maintenance

Existing focused checks provide different kinds of evidence:

- [Class help contract](../../tests/async/test_class_helpfiles_contract.py): all
  30 class descriptions and skill topics, required sections, help-index entries,
  and agreement between the two maintained import sources. It checks coverage
  and consistency, not every prose/mechanics claim.
- [Creation availability](../../tests/async/test_creation_availability_contract.py),
  [all-classes override](../../tests/async/test_creation_all_classes_toggle.py),
  and [all-races override](../../tests/async/test_creation_all_races_toggle.py):
  source contracts for configuration, shared gates, and override behavior.
- [Creation prompt journey](../../tests/async/test_creation_prompt_journey.py):
  isolated real Telnet creation, correction, confirmation, and relog scenarios;
  it does not qualify every class or the WebSocket alignment path.
- [Unspecialize guard](../../tests/async/test_unspecialize_guard.py),
  [memorized spell eligibility](../../tests/async/test_memorized_spell_eligibility.py),
  [epic skill level gate](../../tests/async/test_epic_skill_level_gate.py), and
  [frag-cap contract](../../tests/async/test_frag_cap_config_contract.py): focused
  native/source checks of their named rules, not complete progression journeys.
- [Dragoon spellcasting](../../tests/async/test_dragoon_spellcasting.py),
  [paladin balance journey](../../tests/async/run_paladin_balance_journey.py),
  [paladin aura cleanup](../../tests/async/test_paladin_aura_cleanup.py),
  [innate reflection](../../tests/async/test_innate_reflection.py), and
  [innate plane shift](../../tests/async/test_innate_plane_shift.py): examples of
  class/ability-specific checks; inspect each test's fixtures and scope before
  extending its result to the class as a whole.
- [Race innate help synchronization](../../tests/async/test_race_innate_help_sync.py)
  and its [sync script](../../scripts/sync_race_innate_help.py): keep racial
  innate lists in help aligned with their grants.

Run an individual test with `python3 tests/async/test_<name>.py` from the
repository root; the [testing guide](../guides/TESTING.md) explains prerequisites
and isolated journeys. A source contract passing does not establish that a
class's complete acquisition, combat, and persistence lifecycle works.

When changing a class, update its actual rule/registration first, then its
description and skill help in the applicable sources, this reference's roster
or progression statements, and the smallest relevant regression. Check both
help sources for duplicate titles, preserve dynamic sections' ownership, and
verify the current `#L` help links if the parsed file moves. Publish help through
the documented import/refresh procedure only when that operation is authorized.

The help lists describe registered grants; actual learning, ability conditions,
creation transport, and deployed configuration remain separate. The implementation
and focused tests own exact formulas and lifecycle behavior. This reference does
not claim exhaustive balance rankings or live qualification of every class.
