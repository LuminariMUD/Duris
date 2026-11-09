# Skills command browser

Status: implementation and review fixes complete and locally qualified. Delivery status is recorded on PR #599.
Date: 2026-11-02
Estimated effort: about 2 hours; allow 1–3 hours for implementation, help updates,
builds, and focused validation. Intended delivery is one focused PR.

## Tracking

- Issue: [LuminariMUD/Duris #598](https://github.com/LuminariMUD/Duris/issues/598).
- Delivery PR: [#599 — Add skills browser and fix effective skill grants](https://github.com/LuminariMUD/Duris/pull/599).
- Implementation/review-fix history: [PR #599 commits](https://github.com/LuminariMUD/Duris/pull/599/commits).
- Delivery branch: `branch/issue-598-skills-browser` (history retained on PR #599).
- Published plan: [skills-command-browser.md](https://github.com/LuminariMUD/Duris/blob/master/docs/ongoing-projects/skills-command-browser.md).
- Implementation workspace: `/home/aiwithapex/projects/duris-issue-598` (disposable).
- Base branch: `master`.

PR #599 links this issue and plan. The issue remains open until the completed
implementation and review fixes are merged.

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
- Keep the five primary forms above. The staff-only `skills target <name>`
  escape explicitly selects a character when its name collides with a reserved
  word, class, specialization, or ambiguous catalog abbreviation.
- Unknown input and incomplete `skills info` should explain the applicable syntax.
  Filter undefined/internal effect entries out of public skill lookup.
- Generate `skills levels` from the class catalog, with readable headings, a
  legend, and paging or column groups. The current display hard-codes 22 columns
  while the class catalog contains 30 entries. Label this as base-class levels;
  specialization details belong in the class/spec and info views.

## Implementation steps and likely files

1. **Refactor command routing and retain existing personal output.**
   Move `do_skills` from `src/guild/guild.c` to `src/cmd/skills.c`. Make no-argument behavior consistent,
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
   and compatible with the MariaDB help catalog.
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
new registration framework is unnecessary. No database schema changes are needed. Review fixes version the recovery records as described below.

## Proof and acceptance criteria

- [x] Bare `skills` shows personal skills for a mortal and for staff.
- [x] Staff target inspection still works; players cannot inspect other targets.
- [x] Every supported class/spec name resolves correctly, including multiword
  names, Assassin/Thief, exact matches, ambiguous abbreviations, and invalid input.
- [x] Catalogs show correct base/spec unlock levels and caps. Cover a spec-only
  skill, a removed skill, a changed level, and a cap-only change. Bash is a useful
  case: Warrior cap 100, Swordsman cap 70, and no Swashbuckler access.
- [x] Personal/info output uses actual specialization and multiclass rules.
- [x] Existing epic, instrument, and song coverage is preserved; internal effects
  do not appear as public learnable skills.
- [x] Info output combines correct live facts with the matching help topic on
  the MariaDB build. Cover redirects, missing help, and unavailable
  help while retaining the live-data section.
- [x] `skills levels` is staff-only, covers the class catalog, and is readable in
  a normal terminal. `skills reset` no longer takes the obsolete reset path.
- [x] Command help documents the final behavior, and output remains readable with
  colors stripped and with long results passing through the pager.
- [x] Run focused executable regressions and isolated gameplay journeys through
  the actual command dispatcher, including both mortal and staff permissions.
- [x] Run `./scripts/format.sh --check`, `make -C src`, and the relevant existing
  help tests. Qualify the changed command/help paths against both supported
  backends using isolated build/test artifacts. Report any unrun validation;
  hosted CI is not a completion dependency.

## Scope boundaries

This is a command/browser and help-composition change, with the two requested
review fixes restoring existing skill-grant/add effect behavior. Skill balance,
learning, training, and acquisition rules are otherwise unchanged. A full mechanics
audit, wholesale help rewrite, spell-browser redesign, new services, and new
configuration layers are outside this implementation. Production deployment is
a separate operation.

Before completion, reread the diff and remove anything not needed for the five
command forms, specialization browsing, help reuse, documentation, or their proof.

## Implementation progress and handoff

- Implemented the browser in `src/cmd/skills.c`, moving the old handler out of
  guild training code and registering its object in the Makefile. Existing
  command registration and the game output pager remain the entry path.
- Reused `wiki_help_single` directly and declared its existing `trim` utility in
  `wikihelp.h`. No extra help API, description store, eligibility framework,
  configuration, schema, or mechanics changes were needed.
- Class/spec names take precedence over staff target lookup. The staff-only
  `skills target <name>` escape handles characters named like classes or reserved
  words. Current specialization names override legacy Assassin/Thief classes.
- `skills levels` now groups all 30 class catalog entries into six-column blocks.
  Base-class tables and catalogs exclude epic purchases; epic info identifies
  their separate acquisition rules and reuses their help topic.
- Updated both maintained Skills help topics with all command forms and examples.
  Inspection of both help sources found matching topics for every defined skill
  name except the two internal cooldown entries, which the public filter excludes.
- Reviewed the code and the real color-stripped Bash info and level-table output.
  Runtime transcripts are generated under `bin/tests/skills-info-<backend>.txt`
  and `bin/tests/skills-levels-<backend>.txt`, and are not committed.

### Validation completed on 2026-11-02

- `python3 tests/async/test_skills_command.py` — passed on the MariaDB build
  with AddressSanitizer and UndefinedBehaviorSanitizer. Exercises all class/spec
  names, exact/unique/ambiguous matching, specialization-only skills, removals,
  cap/level changes, real character/multiclass calculations, mental anguish,
  mortal/fogged-staff permission boundaries, NPC inspection, epic/instrument/song
  coverage, and retention of live facts with missing/unavailable help.
- `make -C src -j6` — passed; MariaDB binary `bin/server/dms_new`.

- `tests/async/with_disposable_mariadb.sh python3 tests/async/run_skills_command_journey.py --backend mariadb --server bin/server/dms_new`
  — passed the same journey using a disposable loopback database and maintained
  help import. No configured game account, production database, or live server was used.
- `python3 tests/async/test_help_cache.py` — passed, including redirect handling,
  missing/unavailable topics, refresh publication and failure/shutdown behavior.
- `python3 tests/async/test_flatfile_help_catalog.py` — passed catalog, help
  runtime, and information runtime checks.
- `python3 scripts/format_help_topics.py`, `./scripts/format.sh --check`, and
  `git diff --cached --check` — passed. The staged formatter was also applied.
- Pre-commit clang-tidy passed with its compiler include selection pinned to the
  build's GCC 13 installation (`--gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13`).
  Its default selection of separately installed GCC 16 headers caused parser
  errors; an untracked wrapper under `bin/tidy/` supplies the compatible selection
  through `CLANG_TIDY`. No checks were bypassed.

All implementation acceptance criteria above are met. Implementation, tests, and
review fixes are committed and pushed. PR #599 targets `master` and closes issue
#598 on merge; its delivery status and final commit are recorded on that PR. No
implementation work remains in this plan. Production deployment is separate.

## Review resolution and final validation

- Rebased onto master `901fa03bb`, then onto `f71d91345` after concurrent help/news
  and deployment-documentation changes landed. Those changes do not overlap the
  reviewed runtime implementation.
  Keep the reviewed feature and its requested fixes on PR #599, with a separate
  review-fix commit. No release tag or additional PR stack is needed.
- Both findings are valid: runtime effect selectors were bytes despite skill IDs
  beginning at 1000, and the normal getter discarded accumulated modifiers.
- Widen runtime selectors to 16 bits and apply modifiers in the common return
  path. Use the former padding byte in the native copyover affect record and the
  reserved byte in world-recovery wire affects for the high selector byte. This
  preserves existing widths/field offsets. Copyover v19 ignores old padding in
  v12-v18; world-record v2 retains decoding of v1 (which wrote zero there).
- Applied effect modifiers in the common return path, including zero-floor handling,
  while preserving the learned rating. Stance-only bonus arithmetic adds to the
  effect modifier rather than overwriting it.
- Both findings are fully addressed. Existing truncated selectors cannot be
  generically reconstructed; old records retain their original low-byte value.
  Existing set-bonus effects are NOSAVE and are regenerated by their normal path.
  New copyover/world records require the updated reader (v19 / record v2); the
  updated reader continues to accept v12-v18 / record v1.

Additional local proof after the review fixes:

- `python3 tests/async/test_skills_command.py` — ASan/UBSan passed on MariaDB;
  full skill IDs, grant/add/negative/unrelated effects, removal, unlearned ratings,
  unchanged learned values, and updated `skills info` effective ratings.
- `python3 tests/async/test_world_recovery_codec.py` — passed new full-width and
  legacy low-byte affect wire round trips and v1/v2 record header compatibility.
- `python3 tests/async/test_copyover_evidence.py` — passed v12-v19 native readers,
  ignored poisoned old padding, full v19 selectors, and bounded evidence scenarios.
- `python3 tests/async/test_copyover_custody.py` — passed actual production
  save/exec/recover with a full-width skill effect materialized on the restored NPC,
  alongside existing item/custody, shop stock and concurrent-publication cases.
- `python3 tests/async/test_world_recovery_pipeline.py` — passed immutable snapshot,
  publication, rollback, floor handoff, framing and restored-item behavior.
- `python3 tests/async/test_world_recovery_npc_items.py` — passed NPC item rehydration.
- `python3 tests/async/test_telemetry_copyover_format.py` and
  `python3 tests/async/test_shopkeeper_copyover_compat.py` — passed existing handoff
  and historical-format compatibility checks.
- The MariaDB build and isolated mortal/staff skills journey listed
  above passed after the fixes. Formatting, diff checks and pre-commit clang-tidy
  pass with the documented GCC 13 header selection.

No production state was changed, no release tag is appropriate, and no additional
stacked PR is needed. The single PR retains the browser and review-fix history. Squash-merge it as one
coherent change, then retire its delivery branch and disposable workspace once
integration is verified. Hosted CI is not a completion gate; the applicable
checks above ran locally.
