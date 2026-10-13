# Character mechanics: explicit connections in gameplay code

Status: **active, resumed at the user's request on 2026-10-13**. Work is on
`feature/52-character-mechanics`, based on
`7a2a6344727b3cdd63851bde37f6a5a2d67aeb8d`. The full acceptance scope below remains
open. Original source inspection: 2026-10-12; implementation started 2026-10-13.

Tracking issue: [#52 — Make character mechanics explicitly connected and mechanically traceable](https://github.com/LuminariMUD/Duris/issues/52).

## Current work and continuation

- The worktree started clean, matching the published feature branch and
  `origin/master`. Keep all implementation on this worktree. Another session may
  use the shared local/dev game; use isolated harnesses and disposable servers,
  without stopping or modifying that instance or its database/Redis state.
- Step 1 is active and incomplete; steps 2–4 remain required. The compiled identity foundation
  below is implemented; next complete Guardian/Bulwark, ordered multiclass, and
  Revenant traces. Do not treat an inventory as completion of these traces.
- Separately scoped defect repaired in `86de3042a` while connecting specialization eligibility:
  `is_allowed_race_spec` scanned a 265-row table using a nonexistent sentinel.
  A denied Thri-Kreen Guardian selection reproduced an ASan global-buffer-overflow
  at `specializations.c:452`. Repair uses a range loop over the existing array,
  preserving matching rules and the all-classes bypass. The focused native test
  compiles the complete production translation unit and checks explicit grants,
  denials, override, and exhaustive defined race/class/slot traversal under
  ASan/UBSan. `python3 tests/async/test_specialization_eligibility.py`,
  `python3 tests/async/test_creation_all_classes_toggle.py`,
  `./scripts/format.sh --check`, and `make -C src -j8` passed. Before-fix ASan
  evidence is local at `bin/tests/specialization-before.log`. Full completion
  gates remain pending.
- Ablation: retain production tables and their actual bounds instead of adding
  another roster or evaluator. No registration framework, export format, or
  runtime gameplay dispatch is needed. Every retained connection still needs
  reverse coverage and appropriately scoped behavior/lifecycle evidence.

### Resume work

Resumed from clean, published checkpoint `95bcf2e82`. The issue scope is unchanged;
`origin/master` remains the original baseline. Current work adds the first typed
`MechanicConnection` records to the existing header/source, with providers beside
innate and combat owners. Six IDs connect effective innate identity, unlock,
eligibility, the Guardian grant cell, the loaded factor, and the real melee handler.
Compiled markers bind the exact grant, property load, and shield/effect statements.
Access, implementation state and proof remain independent; no proof flag is saved.

Outcome for this slice: a connected and testable passive chain plus a reverse
tripwire that rejects an unowned/missing passive site. Non-goals: moving gameplay
rules or claiming creation/teacher/lifecycle completion. Files are the existing
contract pair, `innates.c`, `fight.c`, and the existing native tests (Reflection
needs the marker header in its extracted-code fixture). Proof is the existing
Bulwark executable fixture, compiled connection validation, source mutation cases,
formatting, and the server build. No generalized dispatcher or registry is added.
This passive slice is implemented and locally validated. It changes no gameplay
decision: the production additions are descriptors and compile-time site markers.
`CHARACTER_MECHANIC_BIND` keeps native pointer types and stringifies the same
symbol for source checks; there is no type-erased invocation API. The aggregate
validates ID uniqueness/completeness, dependency resolution, owner identities,
binding types, and gap/state consistency. Native output prints the actual
connections, dependency edges and declaration locations.

The reverse check scans maintained C/C++ sources and headers for the migrated
Bulwark identities. It recognizes the three exact current statement forms and
their compiled markers, plus numeric definitions and typed descriptor
initializers. Unsupported reshaping requires review; a marker cannot absorb a
new nested branch. The checker currently covers **Bulwark only**, not every
innate/helper caller or the remaining option families. That broader migration
remains required; no baseline exemption list was introduced.

Validation after resume:

- `python3 tests/async/test_character_mechanics.py`: passed under ASan/UBSan.
  Source fixtures under `bin/` detect consumer removal, marker removal, new
  source-file use, a new macro alias, and a nested branch. Compiled mutation
  fixtures also prove that a stubbed damage effect and changed property fallback
  fail the native damage assertion. The positive native binary SHA256 was
  `632a900a2258dad790c1a721d010916d566783accce3eec0379ed17692bce6bf`.
- `python3 tests/async/test_innate_reflection.py`: passed; its extraction fixture
  includes the new marker header and retains its original dispatch/cooldown scope.
- `make -C src -j8`, `make -j8 build-production build-editor`, and
  `make -C src -j4 pfile`: passed.
- `./scripts/format.sh --check` and `git diff --check`: passed. Evidence is in
  `bin/tests/character-mechanics-connections.log`,
  `bin/tests/character-mechanics-connections-build.log`,
  `bin/tests/character-mechanics-connections-consumers.log`,
  `bin/tests/character-mechanics-connections-pfile.log`, and
  `bin/tests/character-mechanics-reflection.log`.

**Still open for the first trace:** connect creation and actual specialization
command registration/teacher guards/mutation/skill refresh; bind the passive's
null callback; add the complete applicable save/load path and real damage/command
journey. Grant history/conflict detection and wider reverse coverage also remain
open. The current fixture ends at the raw-damage boundary as described in the
historical checkpoint below. Step 1, all multiclass/Revenant traces, and steps 2–4
are still incomplete. The earlier full gate has not been rerun for these new
descriptors/tests; the final completion gate remains required.

### Historical pause checkpoint

Completed and pushed before this checkpoint:

- `86de3042a` — specialization allowance bounds repair and regression.
- `831fda768` — identity-table/predicate bindings and their native validator.

The subsequent work only extends
`tests/async/test_character_mechanics.py` and
`tests/async/character_mechanics_harness.cpp`; it changes no production behavior.
It is retained with this pause checkpoint. The extension extracts the actual
`assign_innates`, innate effective-race/unlock/eligibility functions, property
parser/loader/lookups, damage-factor loader, and complete `melee_damage` body into
the existing native test. It uses the committed properties and creation config
in a private directory under `bin/tests/`, with all three mode switches disabled.

`python3 tests/async/test_character_mechanics.py` passed with ASan/UBSan immediately
before the pause. The result is in `bin/tests/character-mechanics-bulwark.log`;
the tested native executable SHA256 was
`2b9a459235937975c2e1ee4d5a0a5c225acc83f73fdd9edf5a28e0699e198b2f`.
Named assertions cover Guardian at level 40/41, shield absent/present, wrong and
unset specialization, class ownership versus a shared slot number/secondary class,
the reduction-bypass flag, the shipped 0.850 factor, and property reload to 0.5.
The observed 1,000-point melee input becomes 850 or 500 when applicable and stays
1,000 on the named denials/bypass paths.

**Evidence boundary:** `raw_damage` is a recording stub. Armor calculation,
unrelated combat services, and randomness are controlled fixtures. These cases
prove the real melee reduction delivered to raw damage, not actual HP/death,
equipment validation, teacher selection, ordinary acquisition, save/load, or a
complete Guardian route. No mechanic/transition record types, compiled branch IDs,
grant-write ledger, or reverse checker were added yet. Do not infer an accepted
graph design from the test extension.

The 729-case full gate below belongs to the foundation and **predates the Bulwark
test extension**; it was not rerun for this pause. The last in-flight focused test
finished successfully, so no test or build from this work remains running. The
shared dev game and its data were not touched.

On explicit resume, inspect the checkpoint diff and this plan, then add the actual
grant/property/eligibility/effect connections beside their owners. Extend the same
test with source-mutation detection for a missing passive consumer and bind named
assertions to the mechanic IDs. Continue through real specialization entry and
lifecycle proof, then the multiclass and Revenant traces and every remaining
acceptance item below. The paused work is not ready for a review PR or release tag.

### Implemented foundation (partial step 1)

`src/player/character_mechanics.h` and `.c` now expose `IdentityConnections`:
read-only spans supplied beside the actual tables in `common.c`, `constant.c`,
and `specializations.c`, and typed references supplied beside the real creation,
specialization, and multiclass predicates. The explicit aggregator neither
dispatches gameplay nor stores copied formulas. Table sentinels are retained so
their removal can be diagnosed. The specialization row type moved to its existing
header without changing layout or table content.

At `831fda768`, `python3 tests/async/test_character_mechanics.py` compiled these complete production
translation units with ASan/UBSan. Its temporary fixture copies the committed
creation configuration, explicitly disables all three mode switches, and never
reads `.env`. It reports the native executable identity and separates structural
binding assertions from named predicate-policy examples. It covers all race names,
all class names, every spec slot including empty/"Not Used" slots, raw creation
and ordered-secondary tables, out-of-player-range forms, normal/override example
results, and malformed-view diagnostics. That foundation alone did **not** establish
mechanic IDs, grant/effect connections, source mutation detection, or command
reachability; the resumed passive work above adds the first limited connections.

Next implementation work remains:

1. Add the actual mechanic/transition relationships and exact compiled branch
   bindings, starting with Guardian/Bulwark, multiclass reset/consumers, and
   Revenant application/reversal/capture/load. Identity views are only their
   shared input; do not claim step 1 complete from the current validator.
2. Add the bounded reverse check to the same test entry, enumerate/classify every
   scoped site, and retain a finite backlog during migration. No broad exclusion
   or automatic whole-file ownership is acceptable.
3. Complete all owner groups, registration-write conflict detection, source
   mutations, and command/lifecycle acceptance in steps 2–4 below. No evidence
   in the identity harness replaces those tests.

Foundation validation on 2026-10-13:

- `make test-all -j8 TEST_JOBS=8`: **729 passed, 0 failed**, no timeouts or
  signal exits, in 748.07 seconds. This includes the development/production
  server builds, area editor/tools/world, focused tests and isolated server
  journeys. Both new native tests are discovered by the existing runner.
- `make -C src -j4 pfile` and
  `make -C migrations/tools -j4 all affects pfile_converter`: passed.
- `./scripts/format.sh --check` and `git diff --check`: passed.
- `CHAOS_MUD=TRUE CREATION_ALL_RACES=TRUE CREATION_ALL_CLASSES=TRUE python3
  tests/async/test_character_mechanics.py`: passed, proving the test establishes
  its normal baseline even with inherited overrides enabled. Its native binary
  SHA256 was `6b1bd7abf95b08fd48abf8a3609333cbb1fa6d5b36d650f325428a785b18c3a2`.
  Native predicate fixtures use client-free compilation and no persistence backend.
- Local evidence is in `bin/tests/character-mechanics-{native,override-isolation,
  test-all,pfile,migration-tools}.log`. These logs and binaries are not committed.
  No database gate was run for these table/predicate bindings; the planned
  progression/database and new lifecycle qualifications remain open.

An initial comment-stripped identity-token scan found 7,716 candidate source lines,
saved locally in `bin/tests/character-mechanics-candidate-sites.txt`. Most are in
classes, core tables/accessors, creation/account, commands, magic, world, combat,
and special procedures. This is only an investigation starting point: it includes
definitions/declarations and misses indirect aliases, some form flags, callbacks,
and lifecycle dependencies. It is **not** reverse coverage or an exemption list.
The bounded reverse check and its mutation proofs remain to be implemented.

All work remains on the feature branch. The foundation is an intermediate commit,
not a release; no release tag or ready-for-review PR is appropriate yet. The
original planning checks at the end of this document are historical evidence only.

## Outcome, boundaries, and proof

Add a small compiled C++ contract connecting character options to their existing
implementations. For any race, class, specialization, ordered multiclass pair, or
transformation route, expose this chain in both directions:

```text
option -> entry route -> eligibility and restrictions
       -> abilities, bonuses and penalties -> implementation and consumers
       -> progression/transformation -> resulting state and lifecycle
       -> specific tests and the limits of their evidence
```

Mechanics stay in their appropriate modules. The reverse direction is mandatory:
option-dependent gameplay sites and identity changes must identify their
connections or carry a specific reviewed exclusion. An index that only points to
functions does not satisfy the task.

**Normal play:** explicitly set `CHAOS_MUD=FALSE`, `CREATION_ALL_RACES=FALSE`, and
`CREATION_ALL_CLASSES=FALSE`; use the checked-in
[creation configuration](../../lib/creation_availability.cfg),
[properties](../../lib/duris.properties), and world selected by
[areas/AREA](../../areas/AREA). This is a reproducible repository baseline, not a
claim about a deployed server. Tests override inherited switches and use isolated
configuration without reading `.env`. Record the persistence backend and explicit
fixtures for live progression state, including side-specific level caps/timers;
the three switches alone do not determine that state. Account admission,
invitations, alignment,
faction, level, equipment, and world requirements remain separate conditions.
Staff grants and Chaos rewards do not establish ordinary acquisition. Creation
switches must not become new restrictions on existing characters or progression.

**Non-goals for the connection migration:** changing balance, enabling disabled
routes, fixing discovered mechanical defects, changing storage formats, or consolidating all character
code. No JSON catalogue, export scripts, service, database registry, plugin
system, rules language, or generic transition engine. Documentation consumes the
code structure and test evidence. The current implementation request authorizes
autonomous defect repair; keep such repairs in separately scoped commits, as with
the specialization bounds fix above.

**Files:** implementation adds
one small header/source pair under `src/player/`, changes existing mechanic owners,
and adds focused checks through the existing test runner.

**Proof:** compiled connection validation, reverse coverage checks, native tests
of actual rules/effects, and mortal command/lifecycle journeys. Passing structural
checks cannot establish that a whole option works.

## Source evidence and structures to reuse

These are inspected source findings, not completed gameplay qualification.

| Existing structure | Concrete finding and consequence |
| --- | --- |
| [defines.h](../../src/core/defines.h), [common.c](../../src/core/common.c), [constant.c](../../src/core/constant.c): IDs, names, `playable_races`, `restricted_races`, `class_table` | Normal creation has 21 roster entries. Other races remain defined; Agathinon/Eladrin lie beyond `RACE_PLAYER_MAX`. Class flags differ from table indices. Derive identities from existing definitions and include transformation targets, rather than freezing a second roster or those counts. |
| [creation_availability_config.c](../../src/account/creation_availability_config.c): `creation_*` helpers | Missing option switches default to enabled; committed configuration disables Dragoon. All-classes bypasses class switches and forbidden race/class cells. Restricted class rows apply with all-races enabled. Keep definition, roster membership, configuration permission, legal cell, and accepted entry route distinct. Preserve `class_table`'s NPC consumer in [random.mob.c](../../src/world/random.mob.c). |
| [nanny.c](../../src/account/nanny.c) and [ws_handlers.c](../../src/net/ws_handlers.c): creation | Telnet supports neutral alignment and table codes 2/3/4; WebSocket derives good/evil alignment from faction. For example, Human Necromancer has an evil class cell, but WebSocket assigns Human good alignment before rejecting an evil-only class. Bind both routes and their admission dependencies; characterize this discrepancy without silently normalizing it. |
| [specializations.c](../../src/classes/specializations.c): `allowed_race_specs`, `is_allowed_race_spec`, `do_specialize`; `specdata` in `common.c` | Selection requires a permitted race/class/slot, level 30, suitable teacher, no existing specialization/multiclass, and expiry of `time_unspecced`. Dragoon has teacher exceptions. Success assigns `player.spec` and calls `update_skills`. All-classes also bypasses the race/spec predicate. Bind all these connections, not just the name. |
| [skills.c](../../src/classes/skills.c): `initialize_skills`, `SPELL_CREATE`, `SKILL_CREATE`, `*_ADD`; [structs.h](../../src/core/structs.h): `s_skill`, `ClassSkillInfo` | Existing registration already connects ability IDs, spell callbacks, class/spec requirements, and caps. `rlevel` means a skill level or spell circle. Enumerate actual initialized structures and registration provenance. Ordinary skills have no spell callback; they need their command or passive implementation linked separately. |
| [innates.c](../../src/classes/innates.c): `assign_innates`, `innates_data`, `has_innate` | Grants have unlock levels. Active innates have callbacks; passives have null callbacks and consumers elsewhere. `innate_char_race` handles shape disguise and corpseform specially. Connect grant, effective-identity rule, dispatcher/passive consumer, and effect. |
| [db.c](../../src/world/db.c): `update_stat_data`; [affects.c](../../src/magic/affects.c): `apply_affs`, `calculate_hitpoints2`; [limits.c](../../src/world/limits.c) | Race properties populate `stat_factor`; equipment can substitute individual racial stat factors. Hit points use racial constitution and class modifiers, choosing the larger class modifier for a multiclass PC. Vitality, aging, and level progression have separate consumers. Connect inputs, property defaults, calculations, and results; include conditional [racewar stat modifiers](../../src/combat/racewar_stat_mods.c). |
| [utility.c](../../src/core/utility.c): `GET_CLASS`, `GET_PRIME_CLASS`, `SKILL_DATA_ALL`; [utils.h](../../src/core/utils.h): `GET_SPEC`, race accessors | `GET_CLASS` includes secondary class; `GET_SPEC` tests primary class and slot. Secondary-only skill requirements increase by 5 and use separate cap properties. True, displayed, and effective race also differ. Preserve these distinctions instead of introducing one generic class/race interpretation. |
| [guild.c](../../src/guild/guild.c), [memorize.c](../../src/classes/memorize.c), [epic_skills.c](../../src/classes/epic_skills.c) | Skill updates, practice, spell acquisition, memorization, and use complete the grant chain. Epic rewards already connect classes, teachers, costs, prerequisites, and committed purchase callbacks. Multiclass affects learning costs and memorization. Reuse these structures and connect their consumers/callbacks. |
| [frag_cap_config.c](../../src/combat/frag_cap_config.c), [limits.c](../../src/world/limits.c): `gain_exp`; [sql.c](../../src/sql/sql.c): `sql_level_cap`; [maintenance_repository.c](../../src/persistence/maintenance_repository.c): `execute_level_cap` | Progression depends on side-specific caps, qualifying frags, timers, and Hardcore allowance. Spell-circle unlocks apply across sides. The client-free SQL branch returns the configured floor instead of the live side cap. Connect these restrictions to level-dependent options; an isolated flat-file fixture cannot prove the live cap lifecycle. Reuse [frag_cap.cfg](../../lib/frag_cap.cfg) and existing cap tests. |
| [paladins.c](../../src/classes/paladins.c): Blood Tithe; [dam_mods.c](../../src/combat/dam_mods.c), `fight.c`, `nanny.c` | A class/spec spell grant connects to an affect, damage charging, a periodic decay callback, group damage consumers, and login event rescheduling. Morph identity matters here too. This is a concrete case where a handler binding alone misses essential consumers and lifecycle dependencies. |
| [handler.c](../../src/world/handler.c): item predicates; [actobj.c](../../src/cmd/actobj.c); [mount.c](../../src/classes/mount.c) | Item race/class restrictions and body-dependent wear/mount rules are separate mechanics. Horse body prevents mounting and has other combat consumers. Register restrictions as well as benefits, with each actual consumer identified. |

### Three connections to establish first

1. **Human Warrior / Guardian / Bulwark.** The creation cell and switches,
   race/spec row, teacher command, and `SPEC_GUARDIAN` lead to
   `INNATE_GUARDIANS_BULWARK` at level 41. [fight.c](../../src/combat/fight.c)
   applies it to a victim wearing a shield using
   `dam_factor[DF_GUARDIANS_BULWARK]`, loaded from
   `damage.reduction.guardians.bulwark` (committed value `0.850`). Expose the grant,
   shield condition, loader, damage branch, and boundary/effect assertions. Its
   null innate callback is correct for a passive.
2. **Human/Orc multiclass.** `allowed_secondary_classes` and
   `can_char_multi_to_class` restrict the ordered pair and race/class cell.
   [actoth.c](../../src/cmd/actoth.c): `do_multiclass` lists choices;
   [specs.room.c](../../src/specs/specs.room.c): `multiclass_proc` changes state.
   Baseline requirements are level 50 and 0 epics; the epic requirement is a
   threshold, not an automatic charge. List/room fallback levels differ (41/50).
   The room calls `do_start` before assigning secondary class, clears spec,
   preserves played time, forgets spells, refunds epic skills, and clears trophies.
   Connect [actwiz.c](../../src/cmd/actwiz.c): `do_start_impl` for resets/guild
   effects, then secondary learning/stat consumers and persistence. Display names
   in `multiclass_names` are not eligibility.
3. **Temporary Revenant.** [specs.assign.c](../../src/specs/specs.assign.c) binds
   object 22070 to `revenant_helm` in
   [specs.object.c](../../src/specs/specs.object.c). Its worn-item periodic path
   records the old race in `TAG_RACE_CHANGE`, strips other equipment, changes race
   and age, and schedules `event_revenant_crown`. Removal eventually restores race
   and strips equipment again. The tag has `AFFTYPE_NOSAVE`. Connect application,
   event, generic affect removal, death, and capture/load. Restoring race does not
   imply restoring every field, nor does NOSAVE establish safe relog behavior.

These examples cover data, commands, passives, configuration, resets, asynchronous
work, and reversal without a rules engine.

### Transformations require route and lifecycle connections

| Route | Inspected state; connections to retain |
| --- | --- |
| Ascension | In [actoth.c](../../src/cmd/actoth.c), registered `do_ascend` rejects PCs at `!IS_NPC(ch)`. `ascend_theurgist` rejects NPCs and has no other discovered caller. Preserve Paladin -> Agathinon/Avenger, Theurgist -> Eladrin/Theurgist, and Avenger specialization paths, costs, transaction callbacks, and mutations as disabled contracts. Historical rooms/costs are not usable unlocks. |
| Descension | `do_descend` checks Necromancer/level 50, then returns disabled before its Lich body changes race, secondary class, racewar, hometown, guild, skills, and saved state. `do_old_descend` rejects PCs and has no discovered active registration. Retain its target mappings as legacy; do not infer reachability from `restricted_races` comments. |
| Battlerager and Monk conversion | `berserker_proc_room` in `specs.room.c` changes eligible dwarves to Berserker; `monk_remort` in [specs.mobile.c](../../src/specs/specs.mobile.c) converts certain Clerics. Their assignments in `specs.assign.c` are commented out. Record unbound legacy routes; a class's other acquisition routes are separate. |
| Item forms | Revenant crown is actively assigned. Dragonkin transformation is in `dragonlord_plate_old`; object 25723 instead uses `dragonlord_plate`, which supplies spell effects. The old body's existence does not establish Dragonkin access. |
| Draconic apotheosis | `skills.c` registers a Dragoon spell at circle 12. [magic.c](../../src/magic/magic.c): `spell_draconic_apotheosis` requires a mount, unlinks/removes it, stores old race in an affect, changes race to Dragon, and applies damage. `affects.c`/`fight.c` restore race on lifecycle exits. Creation-disabled Dragoon does not disable the handler for existing Dragoons. |
| Shapechange, disguise, morph | [actnew.c](../../src/cmd/actnew.c): `do_shapechange` uses learned shapes and disguise state consumed by `innate_char_race`. `morph`/`un_morph` instead transfer control to/from an NPC body. [disguise.c](../../src/classes/disguise.c) handles ordinary disguise. Connect their distinct representations, callers, restrictions, and reversals. |
| Affect forms and remort | `magic.c`: `spell_vampire` implements vampire and Theurgist angelic forms through affects, bonuses, pets, and spell slots. [necromancy.c](../../src/classes/necromancy.c): `do_remort` removes these forms when its innate permits. This is distinct from Monk conversion. Include wraith/phantasmal and other mechanically consumed form flags. |
| Corpseform | `spell_corpseform` immediately returns “Temporarily disabled”; a comment identifies a lifecycle problem. Keep grant/dispatch/disabled-body/reversion connections and denial evidence. The comment is a defect-investigation lead, not test proof. |
| World changes | [specs.shabo.c](../../src/specs/specs.shabo.c): `shaboath_alternation_tower` changes race by racewar and schedules reversal, with assignments to rooms 32907–32909. `harpy_good`/`harpy_evil` consume a feather and change race/faction/alignment; mobiles 31109/31124 are assigned. Record actual predicates rather than inferring starting-race requirements from names. |
| Exceptional/admin changes | [spells.c](../../src/magic/spells.c): name-gated `spell_curse_of_yzar` schedules random forms. Also classify staff setters/resets, NPC initialization, legacy loading, and display substitutions. They are exceptional routes or precise exclusions, not silently ignored writes. |

`areas/AREA` includes the relevant Cerebus, Harpy, Shaboath, and multiclass areas.
Assignment/loading is weaker evidence than acquisition. Trace prototypes, resets,
quest/item grants, room access, and real dispatch before claiming ordinary
reachability. Dynamic forms use their actual target table/predicate; do not invent
an exhaustive list of NPC forms. A scan of race assignments alone misses disguise,
control transfer, and affect-based transformations.

## Minimal C++ architecture

### One vocabulary, with definitions beside their owners

Add `src/player/character_mechanics.h` and `.c`: connection types, stable
mechanic/route IDs, enumeration, and structural validation. Existing modules expose
their connections to one explicit aggregator. The aggregator owns no formulas and
does not dispatch gameplay. Avoid self-registration, static-constructor ordering,
virtual providers, and a replacement character model.

Reuse existing IDs. Specializations are `(class, slot)`, with unspecialized slot 0
kept distinct from `specdata` indexing. Rogue Assassin and standalone Assassin
must not collide. Multiclass pairs are ordered; race restrictions attach to the
pair. Transformations are identified by route, not destination alone.

Only two record shapes are needed:

| Record | Content |
| --- | --- |
| Mechanic connection | Stable ID; owning option(s) or existing grant-table reference; relation (eligibility, grant, bonus, restriction, implementation); ability/trait target; production table/function/branch binding; prerequisite/configuration dependencies; relevant context (primary/secondary, true/effective race, level/circle, equipment, mode); specific gap/exclusion if present. |
| Transition connection | Mechanic connection plus entry binding, source/target identities or target provider, eligibility/mutation/commit owners, changed and retained state, permanent/temporary/disguise/control-transfer category, cleanup/reversion and persistence owners. |

Use native typed references to production symbols/tables wherever available and
preserve callback signatures. For a rule inside a larger function, place a compiled
mechanic site ID on its exact guard/effect block and connect that site to its owner.
A filename or prose comment alone is not an implementation binding. The index only
enumerates references; no universal callback context or type-erased dispatcher is
needed.

Values and decisions stay in their current production representation. Expose the
existing value, property lookup, or predicate. Do not copy formulas or eligibility
into strings for a second evaluator. Explanations describe rules; they cannot
establish permission or proof.

### Bind the existing registration and execution paths

- Enumerate real race/class/spec tables and creation predicates. Add narrow
  read-only access where needed; retain override-only and unused/legacy entries.
- Extend `SPELL_CREATE`, `SKILL_CREATE`, grant functions, and `ADD_*_INNATE` to
  retain connection/source identity at their existing registration sites. The
  validator observes writes as well as final tables, so a conflicting overwrite
  cannot disappear into the last value. Preserve order; identify intentional
  overrides explicitly.
- Reuse spell/innate callbacks. Add missing command links for skills and effect
  links for passives. A character route's actual command/object/mobile/room
  assignment and its contract use the same handler and command/vnum. Removing
  the assignment changes the binding status even if its function remains.
- Identify scattered option-dependent damage, casting, stat, body, equipment,
  training, memorization, and progression branches in place. Connect both selector
  and effect, including property loaders/defaults. Shared traits can have multiple
  consumers; cumulative effects identify relevant ordering/combination.
- Reuse `creation_*`, `is_allowed_race_spec`, `can_char_multi_to_class`,
  `has_innate`, `SKILL_DATA_ALL`, and item predicates. Extract a small named rule
  only when an imperative handler lacks a checkable boundary needed by gameplay
  and native tests. Both use the same implementation. Preserve messages, branch
  order, return values, and side effects. Keep differing transport rules separate.

This makes actual gameplay registration supply the connections and actual code
supply the tested decisions. It does not route every attack through the index.

### Connect transitions without replacing their execution

Existing handlers, events, and epic transaction callbacks remain in charge. One
route identity connects entry, eligibility, submission, commit, recalculation,
reversal, and save/load. Submission alone is not a completed asynchronous change;
include failure/refund paths.

Describe actual changes and retention for race/form, primary/secondary class,
spec, level/experience, stats/size/age, alignment/racewar/hometown, learned/taught
skills, memorized spells/slots, epics/money/items, equipment, pets/mount links,
guild/trophies, timers, and affects. Use existing field/affect IDs and operations;
add no saved “character option” object. Tests assert before/after state through
the real handler. Each route identifies applicable expiry, manual reversal, death,
extraction, quit/relog, restart, and conflicting-form exits.

Reuse [player_snapshot_capture.c](../../src/player/player_snapshot_capture.c),
[player_load_materialize.c](../../src/player/player_load_materialize.c), and existing
snapshot/repository paths. Capture stores `GET_RACE` but excludes NOSAVE affects:
temporary-form persistence needs explicit tests, not an assumed storage repair.

### Check both directions through existing tests

One focused entry, `tests/async/test_character_mechanics.py`, runs the native
validator and a bounded reverse source check using existing test helpers. Add a
`character_mechanics_harness.cpp` alongside it if needed. Normal discovery puts
these checks in `make test`/`make test-all`; the existing build workflow already
runs `make test-all`. No new scripts or CI service are needed. Run checks locally
without waiting for CI.

The compiled validator checks:

- Unique/resolvable IDs, valid class masks/indices/spec slots, table dimensions,
  dependencies, owners, and target providers. Unused slots remain classified.
- Grants connected to acquisition/use or a specific gap; active callbacks, skill
  command paths, passive effect consumers, and actual route registrations.
- Conflicting registrations for the same subject/slot/context without explicit
  precedence; incompatible transition declarations; missing applicable reversal
  or persistence bindings. Legitimate stacking is not a duplicate error.
- Tests bound to real rule IDs and existing cases. Missing tests mean unverified,
  not necessarily missing implementation.

The reverse check scans all maintained `src/`, including new files and headers,
not merely files in the index. Account for race/class/spec IDs and accessors,
macros/aliases, direct identity fields, grants and consumers, relevant form flags,
disguise/morph state, and character-relevant commands/procedure assignments. Follow
abilities to handlers even when a handler has no race/class check. Include their
property loaders and world bindings. Track callers of registered helpers and
aliases too: a new use creates an obligation even without a class/race literal
in the caller.

Every discovered site resolves to a connection, shared dependency, or exact
exclusion with a reason (NPC initialization, display, staff, load, etc.). Exclusions
cannot cover directories or all NPC-shaped characters: a player morph can occupy
an NPC body. New selectors, aliases, writes, grants, handlers, and assignments
create new obligations. Removed or changed binding sites invalidate connections.
A tag on a whole file or large function cannot cover new branches inside it.

Use the existing bounded source-contract helpers as a tripwire. Unsupported forms
must fail with a location for review; do not silently skip them or build a general
C++ parser. This checks source coverage, not arbitrary semantic correctness.
Executable cases check rules/effects; review follows indirect dependencies. Prove
the tripwire with the mutations below rather than assuming token matching is
sufficient. Temporary unclassified sites are migration work, not an acceptable
final state.

## Access, implementation, and evidence

Track three independent dimensions per route/mechanic and derive option summaries:

| Dimension | Meaning |
| --- | --- |
| Access | **Available** at a named entry; **Conditional** on listed requirements; **Disabled/unavailable** with the gate/missing binding; **Unresolved** where reachability is not established. |
| Implementation | **Connected implementation**, **Incomplete** with an identified missing/conflicting component, or **Legacy/placeholder** without a supported path. None implies tested. |
| Proof | **Proven for named assertions**, **Failing**, or **Unverified** for missing/skipped/indirect/stale evidence. Identify structural, native behavioral, command/world, and persistence scope. |

Conditional can coexist with incomplete. Disabled can have a proven denial.
An existing character can use an effect whose creation route is disabled. One
successful test cannot certify a whole class.
These statuses are diagnostic; they add no gameplay gates or rejection of legacy
characters.

Bind assertions to mechanic/route IDs and exact cases, not filenames alone. Record
configuration, fixture scope, production dependencies/callees, and current results.
Only a successful run against the current inputs establishes proof. Reuse existing
build-artifact identity for journeys; native results identify compiled inputs.
Changed code, assertions, relevant properties, or world inputs invalidate prior
proof. Do not store an editable `verified` flag or a separate evidence catalogue.
The native test executable can print its connections and results directly;
documentation cites that output and tested revision. No exporter is needed.

A known gap records its precise rule, binding, reproduction/open question, and
failed/missing assertion. Recognizing an existing gap must keep it visible as
incomplete and must not excuse new or changed failures.

## Migration and acceptance

### 1. Add the contract and establish the inventory

Add the two C++ files to [src/Makefile](../../src/Makefile), expose existing tables,
and connect the three examples above. Classify the remaining options and route
families; enumerate outstanding sites through the reverse check. Numeric IDs,
serialization, and behavior remain unchanged. No database migration is needed.

Accept when all identities are accounted for, including unused specs, restricted
races, forms outside the player range, and legacy classes; each example reaches
its effect and lifecycle; no definition/registration is silently omitted.

### 2. Connect existing owners in bounded groups

Proceed through creation/admission; specialization/training; ability registration
and dispatch; passive/stat/equipment/combat consumers; multiclass/progression;
transformations; cleanup/capture/load. Each group gets its connections and focused
checks. Keep a finite migration backlog and remove its exemptions as work lands.

Accept when every scoped site has ownership or a precise exclusion, every
connection reaches actual code or an identified gap, and no site is unclassified.
Compare pre/post behavior for touched functions with identical fixtures,
configuration, and random inputs. Preserve successes, denials, messages, costs,
mutation order, and persisted results.

### 3. Prove detection, not just a green inventory

Use temporary fixtures under `bin/`, not edits to the running checkout:

| Mutation | Required detection |
| --- | --- |
| Add a race/class/spec, grant, or transformation target without its links | Missing relationship, naming the new option/site. |
| Remove a command, spell, or room/item assignment but leave its function | Binding failure; no remaining accessible-route claim. |
| Leave a passive grant but remove its effect consumer | Missing implementation; grant-table coverage is insufficient. |
| Add a class/race/spec branch or direct identity write in a new file, including through a new alias | Unregistered site; existing owner/exclusion tags cannot absorb it. |
| Overwrite a grant cell with incompatible data | Conflict before final-table overwrite hides it; explicit existing precedence remains valid. |
| Change a prerequisite/property/target/callback/cleanup dependency | Stale proof and a failing relevant behavioral assertion when outcomes change. |
| Remove/rename/skip a test or stub the implementation it claims to prove | Missing test binding or unverified result; no stale success promotion. |
| Broaden/remove a gap exemption without resolving its condition | The precise diagnostic/case fails. |

Use real initialized tables and production predicates for exhaustive finite
race/class/spec and ordered-pair checks, including denials and boundary levels or
circles. Test overrides separately and prove a normal baseline does not inherit
the parent's enabled switches. Oracles use independently specified outcomes and
actual entry behavior, not a second copy of production formulas.

### 4. Qualify actual routes and lifecycle

Extend relevant tests and
[test_creation_prompt_journey.py](../../tests/async/test_creation_prompt_journey.py).
Add one `test_character_mechanics_journey.py` for mechanics that do not fit it.
Reuse isolated servers, clients, build artifacts, and full-world fixtures.

| Family | Behavioral acceptance |
| --- | --- |
| Creation | Telnet and WebSocket menus/submissions; legal and forbidden race/class/alignment; disabled Dragoon/restricted races; admission denial; starter kit/abilities; save/relog. Characterize transport differences rather than correcting them incidentally. |
| Specialization | Real mortal teacher command at/below 30; wrong teacher/race/slot, existing spec/multiclass/timer denials; resulting spec and skills; relog. Unspecialize covers funds, submission/commit failure, successful cost/reset, and spell removal. |
| Effects and restrictions | Guardian at 40/41, with/without shield, correct/wrong spec, through actual damage application; active innate dispatch/cooldown/effect; racial stats and body/item restrictions. Cover primary/secondary and effective-race differences. |
| Multiclass | Assigned room path for both races; invalid race/pair/morph, repeat and threshold denials; before/after identity, level, experience, skills/spells/epics/guild/trophies; secondary learning/caps/stat effects; save/relog. |
| Level progression | Side-cap and Hardcore restrictions, level/circle boundaries, and resulting ability eligibility. Reuse the existing isolated level-cap database tests for qualifying-frag/timer/unlock/persistence behavior; keep flat-file fixture evidence separate. |
| Disabled/legacy routes | Actual ascend, descend, and corpseform denial without mutation/consumption/cost. Callable helpers do not activate unassigned Battlerager/Monk/old Dragonlord routes. |
| Transformations | Each distinct state representation enters through its real route, changes the recorded state, supplies an observable resulting mechanic, and exits correctly through applicable removal/expiry/death/relog/restart/conflict paths. Include item, shape/disguise, control-transfer, affect, world, and permanent changes. Separate existing-character-only use from new-character reachability. |
| Acquisition | Check assigned/loaded world content plus trainer/item/room prerequisites for normally reachable routes. Spawned items, synthetic teachers, staff grants, and teleportation prove only narrower handler fixtures. Unfinished acquisition remains unresolved. |

Every rule requires ownership and a declared proof obligation. Run cases for all
moved/extracted behavior and each distinct transition lifecycle. Shared evidence
must enumerate the options it covers. Untouched mechanics can remain explicitly
unverified, and discovered defects incomplete; missing structural coverage or
refactor-preservation tests cannot be hidden in those statuses.

Reuse existing evidence at its actual scope:

- [test_creation_availability_contract.py](../../tests/async/test_creation_availability_contract.py)
  and creation override tests mostly check source wiring, not full creation.
- [test_innate_reflection.py](../../tests/async/test_innate_reflection.py) executes
  grants/eligibility/dispatch/cooldown but stubs the spell effect.
- [test_unspecialize_guard.py](../../tests/async/test_unspecialize_guard.py) checks
  invalid-state charging; its commit callback is stubbed.
- [test_item_race_restriction_runtime.py](../../tests/async/test_item_race_restriction_runtime.py)
  executes real item race predicates, not every equipment/body restriction.
- Race/class help coverage and
  [test_race_innate_help_sync.py](../../tests/async/test_race_innate_help_sync.py)
  establish documentation properties, not playable mechanics.

Implementation completion commands include the new contract/journey tests,
relevant extended tests, `./scripts/format.sh --check`, and `make -C src`.
Shared registration macros/headers also require their `_DE_`/`_PFILE_` consumers
and maintained build targets checked. Follow [TESTING.md](../guides/TESTING.md),
including `make test-all`; use isolated database journeys where the touched path
requires them. Report failed/skipped/unavailable checks precisely. No production
operations belong to this migration.

## Gameplay findings stay separate

The Human Necromancer transport mismatch needs a behavioral characterization.
Disabled ascent/descent and commented-out assignments are access facts, not
permission to enable them. Different multiclass defaults and identity accessors
must remain visible. Temporary race plus NOSAVE affect persistence requires a
save/reload reproduction before declaring a defect. Comments are not test proof.

Record failures against their connections, distinguishing reproduced defects,
open questions, and deliberate policy. Repairs require separately scoped gameplay
changes. This migration can expose incomplete mechanics while preserving them;
it cannot mark them proven to make the structural checks green.

## Ablation and completion

Keep the compiled vocabulary for shared identities/relationships, bindings at
actual gameplay sites to prevent a detached catalogue, reverse checks to find
unregistered code, and executable/lifecycle tests to establish behavior.

Drop the former plan's proposed JSON evidence file, source-table extraction
generator, and documentation-first architecture. Reuse production tables and tests.
Keep only extractions necessary for a shared, checkable production rule. No
exporter, alternate evaluator, general transition framework, or wholesale move.

Complete means every scoped option/site is accounted for; eligibility, abilities,
bonuses, restrictions, implementations, progression, and state/lifecycle changes
are connected; mutation checks detect missing/conflicting/stale/unregistered links;
and proof is current and limited to its assertions. Documentation explains this
code structure. This plan authorizes no implementation by itself.

Historical planning validation (before implementation): all 57 local source/document links resolved, scope/revision
and whitespace checks passed, and these existing focused commands passed:

```bash
python3 tests/async/test_creation_availability_contract.py
python3 tests/async/test_innate_reflection.py
python3 tests/async/test_unspecialize_guard.py
python3 tests/async/test_item_race_restriction_runtime.py
python3 tests/async/test_frag_cap_config_contract.py
```

Their evidence is limited as described above; the frag-cap test is a source
contract. No full build, database test, or gameplay journey was run for that
document-only change. At that checkpoint the proposed contract and acceptance
tests did not yet exist; the current implementation and evidence are recorded
in the continuation and pause sections above.
