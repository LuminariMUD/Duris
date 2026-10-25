# Help authoring guide

Use the current command, ability registration, handler, and configuration as the
source of truth. Describe what a player can do now. Omit disabled recipes,
superseded behavior, capture transcripts, and claims based only on a class name.

## Source files and precedence

- `help/duris_help_parsed.hlp` holds complete player-help topics separated by
  `#0` on its own line. Each topic starts with a short title line followed by
  the full title line shown below. The importer derives the title from the
  second line, so both lines must be present.
- `lib/information/help_index` holds topics separated by `#`. Its first line
  supplies the title, with an optional parenthesized type. Quote a title whose
  parentheses are part of the actual name.
- A matching parsed-help title wins over the help index during import. Check
  both sources before editing, and keep overlapping maintained entries consistent.
- Do not put a new Rules copy in parsed help: `lib/information/rules` owns it.

See [HELP_SYSTEM.md](HELP_SYSTEM.md) for the import and serving paths.

## Parsed topic format

```text
Topic title
Topic title - Last Edited: YYYY-MM-DD
============================================================
Current description and usable syntax.

==See also==

* Related topic
#0
```

Do not add author or contributor attributions. A date identifies the content
revision, not proof of deployment. Preserve the importer's two-line title shape.
Do not include captured prompts or the unrelated search results printed by a
previous help lookup inside the topic body.

## Section layout

Place exactly one blank line before a `==Section==` heading (when it follows
other content) and one blank line after it. This includes `==Description==`,
`==Syntax==`, `==See also==`, racial statistics, and class progression headings.
Preserve topic delimiters (`#0` in parsed help; `#` in the index), title lines,
existing paragraph breaks and any deliberate colours outside progression labels.
Run `python3 scripts/format_help_topics.py` when modifying help content;
use `--write` to normalise the two maintained sources without changing prose.

## Describe the actual rule

Use short, readable prose. Start with the command's purpose and usable syntax.
Include requirements, targets, costs, failure conditions, duration, and reversal
when those details affect a player's decision. Explain disabled commands directly
without an item list, altar recipe, or cost that cannot activate them.

For spells, a compact header can expose the useful facts:

```text
* Area of effect: <actual supported targets>
* Aggressive:     <Yes / No>
* Cumulative:     <actual stacking behavior>
* Duration:       <actual lifetime or Instantaneous>
* Type of spell:  <actual damage/effect type>
```

There is no universal duration or stacking rule for a damage-over-time, healing,
wall, or protection spell. Trace the registration and handler before selecting
these values. A tick, combat round, pulse, and real-time second are different
units; use the unit the effect actually follows. Do not substitute one for another
for stylistic consistency. State uncertainty instead of inventing a duration.

Use game terms such as caster, recipient, victim, hit points, level, spell circle,
and epic points. Implementation names belong in developer references unless they
are also the player's syntax. State stat dependencies only after checking the
handler and its relevant helper calls; command attribute metadata is a separate
maintained input, not an automatic analysis of the implementation.

## Classes, races, and specializations

[CLASSES.md](../reference/CLASSES.md) maps the authoritative tables and current
rules. Distinguish defined IDs from normal creation choices, a permitted matrix
cell from a client's completed creation path, and defined specialization names
from the choices allowed for a particular race.

Class skill lists must distinguish base grants from specialization additions,
removed grants, ordinary skill levels, spell circles, and epic purchases. A
listed requirement does not mean the character has learned or prepared the
ability. Item use follows item masks and body rules; avoid blanket promises that
a class can equip every weapon, armor piece, or artifact.

The importer assigns category `0` to parsed-help and help-index topics. Those
pages need complete authored lists in both database and flat-file builds.
Database pages explicitly assigned dynamic categories receive code-generated
sections: race `25`, class `9`, specialization `16`, and class-skillset `10`.
Do not duplicate those sections in the authored body of a dynamic page.

## Class and specialization progression layout

Use numeric progression rows in both base-class skillsets and specialization
change sections rather than one `ability: circle N` or `ability: level N` entry
per line. Group spells by circle, and skills, songs and instruments by level,
in ascending numeric order; alphabetize names within each group. Render circle
and level labels in bright white (`&+W`) and names in cyan (`&+c`), resetting
at the end of each row (`&n`). Wrap long groups to four-space-indented cyan
continuation lines.

Keep skill caps beside individual skill names (e.g. `parry (cap 90%)`). For
innate additions, use one cyan name per line, a leading `*` for passive
abilities, and `(obtained at level N)` where N is greater than 1, followed by
the passive-ability legend. Order innates by level, then name. Preserve
descriptions, headings, requirements, and all other authored prose.

For the `==Allowed races==` section on both class and specialization pages,
preserve the original class-creation or specialization-permission set, but
print each race with the exact ANSI string in
`race_names_table` (`src/core/common.c`). Use a white `*` bullet and
wrap long lists at 79 visible characters (excluding ANSI codes), indenting
continuation lines by two spaces. This keeps split-colour names such as
Githzerai (`&+WGith&+Gzerai&n`) and Githyanki
(`&+GGith&+Wyanki&n`) intact, while Goblin uses
`&+GGoblin&n`. Preserve the explanation distinguishing character race
permissions from initial creation choices.

For base-class help pages, retain the normal-creation versus event-eligibility
explanation and order existing innate entries by unlock level, displaying each
name in cyan without removing passive markers or unlock levels. Class skillset
pages must retain their base-grant scope and numerical spell/skill requirements,
including the Bard's separate song and instrument lists. The same ANSI format
applies to specialization song changes such as Minstrel's.

Keep both base-class and specialization bodies synchronized across the two
maintained import sources. The historical duplicate `Anti-paladin Skills`
entry is retained for compatibility; the newer `Anti-Paladin Skills` topic
remains authoritative due to parsed-help source order.

For mirrored specialization topics, maintain identical bodies in
`help/duris_help_parsed.hlp` and `lib/information/help_index`.

## Verification and publication

Check title collisions and parser output with
`./scripts/import_help_to_prod.sh --dry-run`. Run the focused class/race/help
contracts for the topics changed; see [HELP_SYSTEM.md](HELP_SYSTEM.md) and
[help-cache.md](../operations/help-cache.md). Confirm that the actual prose and
lists agree with source; structural coverage alone cannot establish accuracy.

Racial innate lists are maintained by `scripts/sync_race_innate_help.py`; its
`--check` mode detects stale lists. Keep command-stat metadata in
`docs/lib/information/command_attributes.txt` and restart after changing it.

A local file edit does not publish database-backed help. Use the documented
import/refresh procedure only for an authorized target. Flat-file help reloads
on restart; database help refreshes through its catalog worker.
