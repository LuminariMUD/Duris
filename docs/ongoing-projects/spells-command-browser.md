# Spells command browser

Status: implemented and locally qualified on MySQL and flat-file backends.
Date: 2026-11-02
Delivery: one focused spells-browser change, followed by the class browser.

## Outcome and sequencing

Give `spells` a player-facing browser consistent with the new `skills` and
`race` commands. Bare `spells` shows the caller's personal spell list for both
players and staff. Move the current staff global catalog to **`spells all`**.
Add class/spec reference catalogs and spell information backed by current game
definitions and existing help.

This work is the prerequisite for the planned class command browser. Its main integration points
are `spells <class or specialization>` and `spells info <spell name>`.
Complete and locally qualify this browser before implementing the class plan.
Follow the [skills browser](skills-command-browser.md) for presentation and
matching conventions, while preserving spell-specific progression and access.

The runtime implementation and maintained help-source updates are complete.
Live help publication and deployment remain separate operations.

## Command forms

- **`spells`**: the caller's personal spell list, including for staff.
- **`spells <class or specialization>`**: the requested base class or complete
  effective specialization spell catalog. Examples: `spells cleric` and
  `spells fire magus`.
- **`spells info <spell name>`**: live spell reference facts, the caller's
  personal access, and the existing helpfile. Example: `spells info fireball`.
- **`spells <target>`**: staff-only inspection using existing visible-character
  targeting. Class/spec names take precedence. **`spells target <name>`**
  explicitly selects a character when its name collides with a class, spec,
  ambiguous catalog abbreviation, or reserved word.
- **`spells all`**: staff-only global reference with spell IDs, aggression
  markers, and base-class circle assignments.

Keep these five primary forms. The explicit `target` escape follows the skills
browser; a separate `levels` or `circles` command is unnecessary for this scope.

## Display and behavior

### Personal spells and staff inspection

- Bare `spells` always selects the caller. Identify whose spells are displayed,
  their class/spec, any secondary class, and their current maximum spell circle.
- Group spells by ascending circle, alphabetically within each circle. Include
  future spells belonging to the character's effective class/spec and distinguish
  them from spells whose circle is already accessible. Do not rely on color
  alone to communicate future access.
- Preserve relevant spellbook presence markers using the existing accessible
  book lookup modes. Display them only where the character's preparation path
  uses them; do not imply that every caster needs a spellbook or uses mana.
- Use the character-specific circle and eligibility calculations, including
  specialization removals and multiclass behavior. Do not substitute a generic
  class catalog or the skill-level helper for the character's spell rules.
- Describe checked facts precisely: class access, circle access, and spellbook
  presence are distinct from preparation and readiness to cast. Do not label a
  spell ready simply because its circle is accessible or it is in a book.
- Preserve staff inspection and identify the inspected target throughout.
  Handle supported NPC targets without accessing player-only state; cover NPC
  handling explicitly during implementation and validation.
- Give noncasters and characters without eligible spells a useful empty state
  and reference syntax. Unknown arguments from ordinary players must produce
  guidance rather than silently redisplaying their own spells.

### Class and specialization catalogs

- Show a canonical colored heading and label a base class or a specialization
  with its parent class. Group entries by circle and then spell name.
- A base-class lookup shows base grants. A specialization lookup shows its
  **complete effective spell set**, with inherited spells, additions, changed
  circles, and removals applied. Include a concise list of spells lost from the
  base class and `spells info <spell name>` navigation.
- Use the initialized class/spec definitions and supported circle bounds.
  Treat zero/invalid circles and removed grants correctly; do not recover a
  removed spell by falling back to the base class.
- Browse independently of the caller's race, level, and class. This is a
  reference catalog, not a creation or specialization-selection check.
- Resolve Assassin and Thief to the current Rogue specializations as `skills`
  does. Exclude empty and `Not Used` specialization names.
- Bard songs and instruments remain in the existing skills browser. Include
  Bard's actual spells here without conflating songs with spell circles.

### Spell information

Present `spells info <spell name>` in this order:

1. **Spell identity**: canonical name, registered aggression, and a useful
   category/type only where current metadata reliably establishes it.
2. **Class/spec availability**: base-class circles and meaningful specialization
   differences, including additions, changed circles, and losses of access.
   Explain that unchanged specializations inherit the listed base behavior.
3. **Your access**: the caller's effective required circle, current maximum
   circle, whether that requirement is met, and relevant spellbook presence.
   If the current character lacks the spell, say so without hiding reference
   information. Where useful, also show the corresponding character unlock level
   derived from the actual circle progression.
4. **Helpfile details**: existing casting syntax, description, effects,
   restrictions, and related topics.

Keep generated facts and authored help in labeled sections. Current definitions
own availability and circles; help supplies the descriptive explanation. Do not
infer damage, duration, cooldowns, final casting time, resource costs, or success
chance from fields that cannot establish those values for the character.

Reuse the help catalog at display time with the resolved full spell name,
honoring aliases and redirects. Add title mappings only for demonstrated
mismatches. Missing or temporarily unavailable help must leave the live facts
and personal-access section usable, with a short explanatory message.

### Staff global catalog

- `spells all` is the explicit replacement for staff's current bare-command
  global dump. Enforce staff access before entering its display path.
- List every defined spell, alphabetically, retaining IDs and aggression
  markers. Skip undefined placeholders and non-spell effect/skill entries.
- Generate base-class assignments from the complete class catalog instead of
  the existing hard-coded subset. Display class codes with required circles and
  a readable legend; wrap assignments and use the existing pager.
- Label this as a **base-class circle reference**. A spell without a base-class
  grant should say so; that alone does not mean it lacks specialization access.
  Direct staff to the info/spec views for those details.
- Keep public catalog/info lookup limited to defined player spell grants,
  including specialization-only grants. Staff can inspect defined unassigned
  spell entries through `spells info` using the name shown in `spells all`;
  label missing ordinary grants explicitly rather than inventing availability.

### Input and presentation

- Follow skills' case-insensitive full-name matching, space/hyphen normalization,
  multiword support, and unique abbreviations. Exact matches win; ambiguous
  input lists candidates instead of choosing the first entry.
- Route reserved forms before class/spec lookup, and class/spec lookup before
  staff target fallback. Keep the explicit `target` escape available for name
  collisions. Reject unsupported trailing arguments and explain missing names.
- Ordinary players must not enter global or target inspection through an
  abbreviation or fallback. Show staff-only syntax only to staff.
- Use the established colored headings, canonical class/spec names, readable
  spacing, and paging. Keep ordinary output within 79 visible columns where
  practical and verify readability after stripping colors.
- Label spell progression as **Circle**. Character unlock level is optional
  explanatory information, not a substitute for circle requirements.
- Retain the existing help sources and output facilities; no second description
  store, new configuration layer, or generic browser framework is needed.

## Implementation steps and likely files

1. **Extract routing and preserve personal behavior.**
   Move `do_spells` from `src/guild/guild.c` into `src/cmd/spells.c`, following
   the skills command layout, and add its object to `src/Makefile`. Retain the
   existing command registration/declaration unless the move needs a narrow
   adjustment. Make no-argument behavior personal, preserve staff targeting,
   and move the global reference behind `all`.
2. **Build the effective reference catalogs.**
   Use `src/classes/skills.c` for initialized grants and
   `src/core/common.c` for class/spec names. Follow the matching and effective
   data approach in `src/cmd/skills.c`. Reuse small helpers where real callers
   justify sharing, without broad command refactoring.
3. **Keep reference and character calculations correct.**
   Inspect `src/classes/memorize.c`, the existing `list_spells` in
   `src/guild/guild.c`, and eligibility helpers in `src/core/utility.c` /
   `src/core/utils.h`. The overload `get_spell_circle(int cls, int spec, int spl)`
   currently serves specialization-only listings; it is not a complete
   specialization catalog. Do not change its meaning for existing help callers.
   Use effective grants for reference views and the character-specific
   calculations for personal views, including the secondary-only circle rule.
4. **Compose spell info and global output.**
   Reuse `wiki_help_single` and the help catalog in `src/cmd/wikihelp.c` /
   `wikihelp.h`. Generate staff class assignments from `CLASS_COUNT` and the
   actual names/grants. Use bounded or dynamic output construction and existing
   paging so a large catalog is not limited by a single fixed-size buffer.
5. **Update documentation and focused coverage.**
   Update the Spells topic in `help/duris_help_parsed.hlp` and
   `lib/information/help_index` through the established content workflow.
   Update relevant guidance in `docs/reference/CLASSES.md` and confirm that
   the class plan's navigation matches the delivered interface. Follow
   `tests/async/test_skills_command.py` and `run_skills_command_journey.py` for
   focused spell tests and isolated real-dispatcher journeys.

No new command registration framework or database schema is needed. Remove the
obsolete commented-out routing inside the moved handler as part of making that
handler readable; preserve unrelated guild, help, and casting behavior.

## Proof and acceptance criteria

- [x] Bare `spells` shows the caller's personal spells for mortals and staff;
  staff no longer receive the global catalog by default.
- [x] Personal output preserves current/future circles, appropriate spellbook
  markers, specialization effects, and multiclass calculations. Cover a
  book-using caster, a different preparation/resource path, and a noncaster.
- [x] Staff target inspection uses the target's data; ordinary players cannot
  inspect targets. Cover visible/absent targets, class/reserved-name collisions,
  the explicit `target` form, and safe NPC handling.
- [x] All supported class/spec names resolve correctly, including multiword,
  exact, unique/ambiguous abbreviation, space/hyphen, and Assassin/Thief cases.
  Invalid and incomplete inputs give useful guidance.
- [x] Class/spec catalogs contain the full effective set. Exercise inherited
  spells, specialization-only spells, changed circles, removed spells, empty
  catalogs, and supported circle boundaries.
- [x] Personal/info access uses actual spell rules, including primary access,
  secondary-only circle adjustment, and the upper-circle boundary. A catalog
  entry or book marker is never presented as proof of readiness to cast.
- [x] Spell info displays correct base/spec circles and losses of access,
  useful personal access, and the intended help. Verify redirects, missing help,
  and unavailable help on both MySQL and flat-file backends.
- [x] Public lookup excludes undefined/internal-only entries while retaining
  specialization-only player spells. Staff info can inspect defined unassigned
  spells from the global catalog with accurate availability labeling.
- [x] `spells all` is staff-only, preserves IDs/aggression, covers all class
  definitions, labels absent base grants correctly, and has a readable legend.
  Permission checks hold for abbreviations, fallback paths, and existing trust
  semantics, including fogged staff where applicable.
- [x] Real-dispatcher journeys cover every command form, mortal/staff behavior,
  navigation, long output, colors, and paging using disposable authority on both
  supported persistence backends.
- [x] Both maintained Spells help topics describe the final interface. Relevant
  skills, race, class-help, spell-eligibility, and help-catalog regressions pass
  for affected paths.
- [x] Run focused executable tests and isolated journeys,
  `./scripts/format.sh --check`, and `make -C src`. Build and qualify the affected
  command/help paths on both MySQL and flat-file backends. Report unrun checks;
  do not wait for hosted CI to finish or merge, and preserve other review
  requirements.

## Scope boundaries

This change is a reference and personal-access browser. Spell balance, grants,
learning, preparation, casting, resource consumption, and multiclass rules remain
owned by their existing systems. It does not add a preparation dashboard, spell
editor, mechanics audit, wholesale help rewrite, or class-browser implementation.

Use local builds and isolated validation data. Live help publication and
deployment are separate operations with their applicable authorization. Before
completion, reread the diff and remove anything not required by the five command
forms, correct data/help composition, navigation, or focused proof.

## Implementation and local qualification

Implemented in `src/cmd/spells.c`, following the existing skills routing and
matching conventions and the race/skills presentation. The guild handler and its
obsolete commented routing were removed; casting and progression calculations
remain in their existing owners. Specialization catalogs read initialized
effective grants, while personal views use the character-specific spell rules.
The standalone Spells topic was added to both maintained help sources, and
Godspells now documents the explicit staff forms.

Validation completed successfully:

- `make -C src -j4`
- `make -C src -j4 PERSISTENCE_BACKEND=flatfile DMS_BINARY=/home/aiwithapex/projects/duris/bin/server/dms_spells_flatfile`
- `python3 tests/async/test_spells_command.py` (both backend variants under
  ASan/UBSan, plus the real flat-file help-unavailable path)
- `python3 tests/async/run_spells_command_journey.py --backend flatfile --server bin/server/dms_spells_flatfile`
- `tests/async/with_disposable_mariadb.sh python3 tests/async/run_spells_command_journey.py --backend mariadb --server bin/server/dms_new`
- `python3 tests/async/test_skills_command.py`
- `python3 tests/async/test_race_command.py`
- `python3 tests/async/test_memorized_spell_eligibility.py`
- `python3 tests/async/test_class_helpfiles_contract.py`
- `python3 tests/async/test_help_cache.py`
- `python3 tests/async/test_flatfile_help_catalog.py`
- `python3 scripts/format_help_topics.py`
- `./scripts/format.sh --check` and `git diff --check`

The real-dispatcher journeys use disposable authority and copied help fixtures
for redirect/missing-help checks. They cover every command form, initialized
catalogs, personal and staff access, NPC collisions, case-insensitive alphabetical
order, colors, 79-column generated output and paging. The class plan's
`spells <class or specialization>` and `spells info <spell name>` navigation
matches the delivered interface. No live server, live database or environment
file was changed.
