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

## Specialization progression layout

Use numeric progression rows in specialization change sections rather than one
`ability: circle N` or `ability: level N` entry per line. Group spells by
circle and skills by level, in ascending numeric order; alphabetize names within
each group. Render circle and level labels in dark blue (`&+b`) and names in
cyan (`&+c`), resetting at the end of each row (`&n`). Wrap long groups to
four-space-indented cyan continuation lines.

Keep skill caps beside individual skill names (e.g. `parry (cap 90%)`). For
innate additions, use one cyan name per line, a leading `*` for passive
abilities, and `(obtained at level N)` where N is greater than 1, followed by
the passive-ability legend. Order innates by level, then name. Preserve
descriptions, headings, requirements, and all other authored prose.

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
