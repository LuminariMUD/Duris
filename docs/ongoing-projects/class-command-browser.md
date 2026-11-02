# Class command browser

Status: implemented and locally qualified on MySQL and flat-file backends.
Date: 2026-11-02
Delivery: focused class browser using the completed race, skills, and spells browsers.

## Outcome and sequencing

Give players a class and specialization guide consistent with `race` and the
new `skills` browser. It should explain playstyle, current creation availability,
specialization paths, and class features, then lead players to the detailed
skill and spell catalogs.

The **spells browser prerequisite is complete**, following the
[spells command plan](spells-command-browser.md). Its confirmed class-browser
integration is:

- `spells <class or specialization>` for the complete effective spell catalog.
- `spells info <spell name>` for individual spell details.
- Matching class/spec names and presentation conventions with `skills`, while
  preserving spell-specific rules such as circles, preparation, and personal
  multiclass calculations.

These commands agree with the implemented `spells` interface. Its personal/staff
behavior remains owned by the spells browser. The class implementation was
authorized by the subsequent implementation request; deployment and live help
publication remain separate.

## Command forms

- **`class` / `class list`**: show the colored class roster with a brief
  description for each entry. Distinguish ordinary creation choices, disabled
  classes, and special/legacy entries.
- **`class list <race>`**: show classes permitted for that race under the current
  creation policy, as the counterpart to `race info <race>`.
- **`class info <class or specialization>`**: show the main profile. Both
  `class info warrior` and `class info guardian` are valid examples.
- **`class specs <class>`**: show its named specializations, a short explanation
  of each path, and the caller's race permission for each.
- **`class innates <class or specialization>`**: show class-granted innates,
  unlock levels, and active/passive indicators, following `race innates`.

Bare `class` is the roster, matching `race`; it does not default to the caller's
class. Missing required names explain the applicable syntax. Keep these command
forms as the initial interface.

## Display and matching rules

### Roster and race filtering

- Use canonical class colors and names, readable headings, short descriptions,
  and the existing output pager. Keep ordinary output within a normal 79-column
  terminal after stripping colors; wrap long race and specialization lists.
- Obtain descriptions from maintained help at display time. Use a neutral
  unavailable-description message when necessary; retain the generated roster.
- Determine availability from the live creation configuration, race roster, and
  shared eligibility functions. A defined class ID alone is not an available
  creation choice. Honor the all-classes/all-races overrides and per-option
  switches, labeling normally restricted choices when an override enables them.
- Resolve race filters using the same player-race naming conventions as `race`.
  Identify the selected race and its creation status. For a disabled or otherwise
  unavailable race, say that no new character can currently select it rather
  than implying that its legal matrix cells make it creatable.
- For an available race, use the same class-policy predicates as `race info`.
  Describe these as current creation-policy choices; transport alignment and
  account-admission checks still belong to character creation.
- Show standalone legacy Assassin/Thief IDs as explicitly labeled legacy notes.
  Resolve ordinary `Assassin` and `Thief` lookups to the Rogue specializations,
  as the skills browser does. Do not advertise an ambiguous legacy lookup.

### Class profiles

Present `class info <class>` in this order:

1. **Identity and playstyle**: canonical name and a short description from help.
2. **Availability**: current creation status, eligible races, and the relevant
   race/class alignment requirements. Alignment is separate from racewar side.
3. **Specializations**: named paths, brief authored descriptions, and commands
   to inspect them. Label the caller's race permission without hiding other paths.
4. **Class features**: a compact innate summary and existing authored explanation
   of distinctive mechanics. Link to the full innate list when needed.
5. **Further reading**: `skills <class>`, `spells <class>`,
   `class innates <class>`, and the relevant class, specialization, and multiclass
   help topics. Generate only navigation supported by the destination command.

Keep the profile useful as an overview. Full skill and spell catalogs remain
owned by their respective browsers. Equipment, resources, and playstyle claims
come from existing descriptive help; do not infer universal equipment rights,
best stats, or performance rankings from a class name.

### Specializations

- A specialization is a full profile target. Show its canonical name, parent
  class, authored focus, race permissions, and selection requirements.
- Class creation eligibility and specialization race permission are separate
  facts. Use the existing specialization predicate, including its configured
  override behavior. Exclude empty and `Not Used` slots.
- Label a personal race check as race permission, not as a promise that the
  caller can specialize now. Explain the existing level, teacher, prior-spec,
  multiclass, and cooldown requirements through current rules and help. The
  `specialize` command remains responsible for selection and its final checks.
- Summarize differences from the base class using effective definitions:
  gained/lost skills and spells, changed skill levels or proficiency caps,
  changed spell circles, and innate changes. Omit unchanged entries from this
  summary; link to `skills <spec>` and `spells <spec>` for complete catalogs.
- Explain distinctive mechanics not represented in grant tables through the
  existing help. Keep authored explanation separate from generated facts.
- `class specs <class>` is the shorter comparison view: name, focus, race
  permission, and `class info <spec>` navigation. Detailed grant differences
  belong in the individual specialization profile.

### Innates

- Reuse the current class/spec innate definitions and listing behavior,
  including inherited class grants where applicable.
- Show unlock levels and the existing active/passive distinction. Do not mix
  racial innates into the class catalog; direct players to `race innates`.
- Include `help <ability name>` navigation for conditions and usage. A listed
  grant does not establish that its equipment or combat conditions are satisfied.
- Display a clear empty state for classes/specs without innates.

### Names and help

- Accept case-insensitive full names, multiword names, normalized spaces/hyphens,
  and unique abbreviations following the skills browser. Exact matches win;
  ambiguous names list candidates rather than selecting the first match.
- Treat subcommands before name lookup and handle ambiguous subcommand prefixes
  explicitly. Invalid input and missing names show useful examples.
- Allow reference browsing regardless of the caller's race, level, or current
  class. Personal annotations do not filter the reference catalog.
- Reuse the existing help catalog on both MySQL and flat-file backends. Honor
  redirects and aliases, and verify that colliding legacy/spec names retrieve
  the intended description.
- Follow the existing race-description approach for extracting authored prose,
  extending the help interface only where the class views need it. Do not parse
  prose into mechanics or copy descriptions into a second store.
- Missing or temporarily unavailable help must leave generated facts usable.

## Implementation map

1. **Finish the spells prerequisite and confirm shared behavior.**
   Read its final command implementation alongside
   [`src/cmd/skills.c`](../../src/cmd/skills.c) and
   [`src/cmd/race.c`](../../src/cmd/race.c). Confirm names, effective class/spec
   data, and supported navigation before writing class code.
2. **Add the command and routing.**
   Add `src/cmd/class.c` and its declaration using the nearby command convention.
   Register it in `src/cmd/interp.c`, `src/cmd/interp.h`, and `src/Makefile`.
   Review the existing command access, abbreviation, and output/paging paths so
   the new reference command behaves like `race` without changing other commands.
3. **Compose roster, profiles, and specialization views.**
   Reuse `src/core/common.c`, `src/core/constant.c`,
   `src/account/creation_availability_config.c`,
   `src/classes/specializations.c`, `src/classes/skills.c`, and
   `src/classes/innates.c` as the relevant authorities. Use the established
   effective grants rather than reconstructing inheritance from source macros.
4. **Reuse help and connect navigation.**
   Make the smallest necessary changes to `src/cmd/wikihelp.c` / `wikihelp.h`.
   Share existing name/data helpers only where the actual callers need them;
   do not introduce a generic browser framework. Update both maintained help
   sources, `help/duris_help_parsed.hlp` and `lib/information/help_index`, with
   the Class command and necessary navigation. Update the command guidance in
   [`docs/reference/CLASSES.md`](../reference/CLASSES.md).
5. **Add focused regressions and dispatcher journeys.**
   Follow `tests/async/test_race_command.py`, `test_skills_command.py`, and their
   isolated journey scripts. Add `test_class_command.py` and a class journey
   only where existing tests do not already cover the behavior. Extend existing
   help checks for the new topic and any description extraction.

No database schema change is expected. Reuse the existing color, help, matching,
and paging facilities; keep helpers local unless there is a real shared caller.

## Proof and acceptance criteria

- [x] The spells browser prerequisite is complete and locally qualified, and
  every advertised spell command agrees with its final interface.
- [x] `class` and `class list` produce the same roster with descriptions and
  correct ordinary, disabled, and special/legacy labels.
- [x] Race-filtered lists agree with the shared creation rules, including
  disabled races/classes, restricted races, both override modes, alignment
  annotations, and empty results.
- [x] Class/spec names resolve consistently with skills and spells. Cover
  multiword names, spacing/hyphens, case, exact/unique/ambiguous matches,
  Assassin/Thief collisions, invalid input, and missing arguments.
- [x] Every named class/spec profile retains its live facts when help is
  missing/unavailable and uses the intended help description when available.
- [x] Specialization profiles show correct additions, removals, changed skill
  levels/caps, spell circles, and innate changes. Include a cap-only case and
  a loss of access; link to complete effective catalogs.
- [x] Reference browsing works for a caller whose race cannot select the class
  or spec. Personal annotations distinguish race permission from full selection
  eligibility; empty and placeholder spec slots never appear.
- [x] Class/spec innates show the correct grants, inheritance, unlock levels,
  and active/passive markers, without racial grants leaking into the list.
- [x] Real-dispatcher journeys exercise roster, filtering, profiles, specs,
  innates, skill/spell navigation, colors, and long-output paging for mortals and
  staff, using disposable authority on both supported persistence backends.
- [x] Both maintained help sources document the final interface and agree.
  Relevant existing race, skills, spells, class-help, and help-catalog checks
  still pass for the touched paths.
- [x] Run `./scripts/format.sh --check`, `make -C src`, focused executable tests,
  and the applicable isolated journeys. Build and qualify affected paths on
  both MySQL and flat-file backends. Report unrun validation; hosted CI is not
  a completion or merge dependency, and other review requirements still apply.

## Scope boundaries

This is a read-only reference browser. Balance, grants, learning, spellcasting,
creation policy, specialization selection, and multiclass mechanics stay owned
by their existing systems. A full mechanics audit, help rewrite, personal build
planner, class ranking system, and new configuration/service layers are outside
this change. Implementing the spells browser is the preceding separate task.

Use isolated validation data. Production operations, help publication to a live
server, and deployment are separate from implementation and require their
applicable authorization. Before finishing the implementation, reread its diff
and remove anything not needed for the agreed commands, accurate data/help,
navigation, or focused proof.


## Local qualification (2026-11-02)

All checks passed against isolated local authority; no production server,
production database, or live help catalog was changed.

- `./scripts/format.sh --check` and `git diff --check`.
- `make -C src -j6` (MySQL), and `make -C src -j6
  PERSISTENCE_BACKEND=flatfile
  DMS_BINARY=/home/aiwithapex/projects/duris/bin/server/dms_class_flatfile`.
- `python3 tests/async/test_class_command.py`: both backend variants under
  ASan/UBSan, all class/spec names, exhaustive race filters and overrides,
  cap-only changes, lost access, spell-circle differences, inherited innates,
  79-column output, and a real unavailable flat-file help catalog.
- Existing `test_race_command.py`, `test_skills_command.py`,
  `test_spells_command.py`, `test_class_helpfiles_contract.py`,
  `test_help_cache.py`, `test_flatfile_help_catalog.py`,
  `test_race_helpfiles_complete.py`, and `test_race_innate_help_sync.py`.
- `python3 tests/async/run_class_command_journey.py --backend flatfile
  --server bin/server/dms_class_flatfile`, and the `--backend mariadb
  --server bin/server/dms_new` variant under
  `tests/async/with_disposable_mariadb.sh`.
- `run_spells_command_journey.py` with the same backend/server combinations
  (the MySQL run also used `with_disposable_mariadb.sh`) requalified the
  prerequisite and navigation destinations.

The class journeys exercise real mortal/staff dispatch, production definitions,
creation status, denied race permission, skill/spell changes, inherited innates,
redirected/missing prose, legacy/spec description collisions, help and catalog
navigation, ANSI colors, 79-column output, and paging for both callers.

The implementation reuses the race display helper and extends its existing
help-prose extraction for named mechanics sections and redirects. It adds no
browser framework, schema, configuration layer, or gameplay-rule changes.
