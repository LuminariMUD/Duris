# Skills command browser

Status: planned; implementation has not started.
Date: 2026-11-02
Estimated effort: about 2 hours; allow 1–3 hours for implementation, help updates,
builds, and focused validation. Intended delivery is one focused PR.

## Tracking

- Issue: [LuminariMUD/Duris #598](https://github.com/LuminariMUD/Duris/issues/598).
- Development branch: [branch/issue-598-skills-browser](https://github.com/LuminariMUD/Duris/tree/branch/issue-598-skills-browser),
  linked to the issue in GitHub's Development section.
- Published plan: [skills-command-browser.md](https://github.com/LuminariMUD/Duris/blob/branch/issue-598-skills-browser/docs/ongoing-projects/skills-command-browser.md).
- Local worktree: `/home/aiwithapex/projects/duris-issue-598`.
- Base branch: `master`.

Keep this issue and plan linked from the eventual implementation PR. The plan
commit documents the work; the issue remains open until implementation and its
acceptance checks are complete.

## Outcome

Give `skills` a player-facing browser consistent with the new `race` command:
readable colored headings, useful name matching, paged output, and information
derived from the game's existing definitions. Keep personal progress, class/spec
reference information, and staff inspection clearly identified in the output.

The scope includes all five command forms discussed:

- **`skills`** — show your own skills, for both players and staff.
- **`skills <class>`** — show that class's base skill set. Also accept a
  specialization's own name, such as `skills guardian`, to show its complete
  skill set with inherited skills and specialization changes applied.
- **`skills info <skill name>`** — show live reference data and your own progress,
  supplemented by the existing helpfile's description, syntax, and other details.
- **`skills <target>`** — staff-only inspection of a visible character using the
  existing targeting rules.
- **`skills levels`** — staff-only class-level reference table, moved out of the
  no-argument path.

Remove the obsolete `skills reset <target>` branch. It currently only looks up a
character and reports that there is nothing to reset.

## Display and matching rules

### Personal skills and staff inspection

- Use the existing personal skill calculation and display as the starting point.
  Preserve proficiency, future unlock levels, learned epic skills, instruments,
  and bard songs already included by `skills`.
- Keep staff inspection's additional training information and identify whose
  skills are being displayed. Bare `skills` must use the caller as the target.
- Respect the inspected character's specialization and multiclass calculations.
  A generic class catalog must not replace character-specific eligibility.
- Preserve supported NPC inspection safely: do not read player-only skill data
  for NPC targets.

### Class and specialization catalogs

- List skills by unlock level, with names and class/spec proficiency caps.
- A class name selects its base definition. A specialization name selects the
  complete effective set for that specialization, including inherited skills,
  changed levels/caps, and removals. Label the specialization and parent class.
- Use live definitions; do not copy availability or caps from help prose.
- Show relevant instrument/song entries where applicable. Ordinary spell lists
  remain under the existing spell commands.
- Treat epic skills according to their existing acquisition rules; do not imply
  they are ordinary automatic class-level unlocks. Preserve their existing
  personal display and allow information lookup for valid epic skills.
- Resolve Assassin and Thief to the current Rogue specializations rather than
  their legacy class entries.
- Browse the requested class/spec independently of the caller's race. This is a
  reference catalog, not a character-creation eligibility check.

### Skill information

Show information in this order:

1. Skill name and any category reliably available from current definitions.
2. Class and specialization availability, required levels, and proficiency caps.
   Show meaningful specialization differences, including cap-only changes and
   loss of access, without repeating identical rows for every specialization.
3. The caller's current proficiency/training and applicable unlock level/cap,
   where meaningful. Use existing character calculations for specialization and
   multiclass behavior. Do not describe a proficiency rating as a guaranteed
   percentage chance of success.
4. The existing help topic, including its usage, explanation, and related topics.

Reuse help content through the existing help catalog at display time. Do not
duplicate help prose into C++ or create a second skill-description store. Use the
resolved full skill name for the help lookup, honoring existing redirects and
aliases. Check actual title mismatches and add mappings only where demonstrated.

Keep generated facts and authored help in labeled sections. The live data is the
authority for levels and caps; the help section supplies descriptive detail.
Do not attempt to parse arbitrary help prose into structured mechanics fields.
If help is missing or temporarily unavailable, still show the live data and a
short explanation that descriptive help is unavailable.

This version reuses the helpfile's existing accuracy. It does not independently
verify every description or infer cooldowns, success formulas, damage, equipment
requirements, or active/passive behavior that the shared skill data cannot prove.

### Input and staff table

- Support case-insensitive full names, multiword names, and unique abbreviations,
  following the `race` command's approach. Prefer exact matches; list candidates
  for ambiguous names instead of choosing the first match.
- Recognize `info` and `levels` before catalog/target lookup. Resolve class/spec
  names before attempting staff target lookup. Ordinary players must never enter
  staff inspection or the staff table through an abbreviation or fallback.
- During implementation, check collisions between reserved/class/spec names and
  character targeting. Keep the five primary forms above; settle any necessary
  explicit staff targeting escape before finalizing the parser.
- Unknown input and incomplete `skills info` should explain the applicable syntax.
  Filter undefined/internal effect entries out of public skill lookup.
- Generate `skills levels` from the class catalog, with readable headings, a
  legend, and paging or column groups. The current display hard-codes 22 columns
  while the class catalog contains 30 entries. Label this as base-class levels;
  specialization details belong in the class/spec and info views.

## Implementation steps and likely files

1. **Refactor command routing and retain existing personal output.**
   Start in `src/guild/guild.c` (`do_skills`). Make no-argument behavior consistent,
   move the staff table behind `levels`, preserve target inspection, and remove
   `reset`. Keep helpers local unless an existing second caller needs them.
2. **Add class/spec browsing and skill lookup.**
   Reuse the definitions in `src/classes/skills.c`, `src/core/common.c`, and the
   existing level/cap calculations in `src/core/utility.c`. Review `list_skills`
   and `wiki_skills` for reusable behavior, especially their specialization
   presentation, rather than introducing parallel eligibility rules.
3. **Compose `skills info`.**
   Use the same definitions for reference facts and the existing help path in
   `src/cmd/wikihelp.c` / `wikihelp.h`. Keep any help presentation adjustment small
   and compatible with both MySQL and flat-file help catalogs.
4. **Update command help and presentation.**
   Update the Skills topic in the repository's help sources
   (`help/duris_help_parsed.hlp` and `lib/information/help_index`) through the
   established content workflow. Document all five forms, specialization names,
   and staff-only access. Follow `src/cmd/race.c` for visual and matching behavior.
5. **Add focused regression and gameplay coverage.**
   Use `tests/async/test_race_command.py` and
   `tests/async/run_race_command_journey.py` as patterns for a skills command test
   and isolated staff/mortal journey. Extend existing help tests where necessary.

The existing `skills` command is already registered; a new top-level command or
new registration framework is unnecessary. No schema changes are anticipated.

## Proof and acceptance criteria

- [ ] Bare `skills` shows personal skills for a mortal and for staff.
- [ ] Staff target inspection still works; players cannot inspect other targets.
- [ ] Every supported class/spec name resolves correctly, including multiword
  names, Assassin/Thief, exact matches, ambiguous abbreviations, and invalid input.
- [ ] Catalogs show correct base/spec unlock levels and caps. Cover a spec-only
  skill, a removed skill, a changed level, and a cap-only change. Bash is a useful
  case: Warrior cap 100, Swordsman cap 70, and no Swashbuckler access.
- [ ] Personal/info output uses actual specialization and multiclass rules.
- [ ] Existing epic, instrument, and song coverage is preserved; internal effects
  do not appear as public learnable skills.
- [ ] Info output combines correct live facts with the matching help topic on
  both MySQL and flat-file builds. Cover redirects, missing help, and unavailable
  help while retaining the live-data section.
- [ ] `skills levels` is staff-only, covers the class catalog, and is readable in
  a normal terminal. `skills reset` no longer takes the obsolete reset path.
- [ ] Command help documents the final behavior, and output remains readable with
  colors stripped and with long results passing through the pager.
- [ ] Run focused executable regressions and isolated gameplay journeys through
  the actual command dispatcher, including both mortal and staff permissions.
- [ ] Run `./scripts/format.sh --check`, `make -C src`, and the relevant existing
  help tests. Qualify the changed command/help paths against both supported
  backends using isolated build/test artifacts. Report any unrun validation;
  hosted CI is not a completion dependency.

## Scope boundaries

This is a command/browser and help-composition change. Skill balance, learning,
training, combat mechanics, and acquisition rules are unchanged. A full mechanics
audit, wholesale help rewrite, spell-browser redesign, new services, and new
configuration layers are outside this implementation. Production deployment is
a separate operation.

Before completion, reread the diff and remove anything not needed for the five
command forms, specialization browsing, help reuse, documentation, or their proof.
