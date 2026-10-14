# Character mechanics: explicit connections in gameplay code

Status: **active, resumed at the user's request on 2026-10-13**. Work is on
`feature/52-character-mechanics`, based on
`7a2a6344727b3cdd63851bde37f6a5a2d67aeb8d`. The full acceptance scope below remains
open. Original source inspection: 2026-10-12; implementation started 2026-10-13.
Latest handoff update: 2026-10-14.

Tracking issue: [#52 — Make character mechanics explicitly connected and mechanically traceable](https://github.com/LuminariMUD/Duris/issues/52).

## Current work and continuation

- The worktree started clean, matching the published feature branch and
  `origin/master`. Keep all implementation on this worktree. Another session may
  use the shared local/dev game; use isolated harnesses and disposable servers,
  without stopping or modifying that instance or its database/Redis state.
- Latest fetch on 2026-10-14: `origin/master` is now
  `0e27ef1e830e18ea648fa400bbc4ce6e8106b06f`, three commits beyond this branch's
  old merge base (statistics persistence and online migration support). Integrated
  as `f75e77b34`, preserving both branches' regression entries at the sole merge
  conflict. Development/production/editor builds, maintenance scheduler and
  migration-runner tests, and the statistics test against a disposable MariaDB
  passed (`bin/tests/character-mechanics-upstream-*.log`). The flight journey will
  run in the next connection gate. The 730-test result below predates this merge.
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

At that checkpoint the command/persistence journey and transition connections
were still open; subsequent work is recorded below. Creation, individual teacher
guards, passive callback registration, complete save/load dependencies, real HP
damage, grant history/conflicts and wider reverse coverage remain open. The
native combat fixture still ends at the raw-damage boundary. Step 1, all
multiclass/Revenant traces, and steps 2–4 are incomplete.

### Specialization entry/persistence journey

The planned `test_character_mechanics_journey.py` is now implemented and its
focused run passes. It reuses the existing verified flat-file server builder,
full-world setup, clients, and disposable authority. It creates a mortal Human
Warrior through Telnet, uses staff-supplied boundary levels and a transfer to the
hall adjoining the loaded teacher Arian, then exercises mortal specialization,
real skill refresh, Bulwark 40/41 visibility, save/relog and restart. The existing
flat-file inspector now exposes primary/secondary class, spec, race and nonzero
skill rows so persistence assertions observe saved state rather than score text.

This is an explicit handler/lifecycle fixture: staff setup does not prove travel
from a hometown or real experience/side-cap progression. As in existing lifecycle
journeys, the private fixture shortens `camp.timer` from 9 to 1; mortal `quit`
dispatches to camping and the original duration exceeded the observation window.
The innate list deliberately shows Bulwark as locked at level 40, so the journey
asserts that label and actual dispatch denial, then the passive response at 41.
No production mechanic
has been changed in this slice. Run evidence is local at
`bin/tests/character-mechanics-journey.log`. It passes missing/wrong teacher,
level-29, wrong-race/spec, multiclass, invalid spec-name and repeated-selection
denials; selects Guardian at 30; verifies Guard and Shield Punch at learned 40 /
taught 100 in the actual saved snapshot; observes Bulwark denial at 40 and passive
dispatch at 41; and preserves the spec/skills through relog and restart. It also
executes the repaired class-None/secondary-None setters through the real command
path. The verified flat-file binary SHA256 is
`0e31e606bce06d776e7b02340bdef24ac75c4e27b243e297a521c28c6fe89c7b`.
The new journey is assigned to the existing
runner's resource-intensive phase rather than competing with native compiles.
The journey was committed and pushed as `9e1d85eb0`. The compiled links built on
this baseline are described in the next section.

A separate repair, committed and pushed as `ec6672d19`, was required while preparing identity-denial fixtures:
`ac_idx2flagCopy` shifted by -1 for the class table's `None` entry, reproduced by
the extended `test_setbit_flag_bits.py`. Following the primary-class update into
`SKILL_DATA_ALL` also reproduced an index -1 read when a secondary class was
present. The copier now maps None to zero; skill lookup applies its existing
Warrior normalization before the PC multiclass branch. Valid pairs, the historical
secondary sentinel and NPC mask enumeration are preserved. Both focused sanitizer
tests pass; before-fix evidence is in `bin/tests/setbit-class-before.log` and
`bin/tests/skill-class-mask-before.log`, with native post-fix evidence in
`bin/tests/skill-class-mask-after.log`. This repair is separate from the new journey.

Validation for the entry/persistence slice and repair:

- The focused native setter and mechanics tests pass with ASan/UBSan. The
  mechanics test now stops on the first UBSan finding. Its positive native binary
  SHA256 is `3cba335b12ce9059ef6bcee5dff50b6b07348296f58f41a3f132423c7000e7d6`.
- `DURIS_REGRESSION_BUILD_CACHE=bin/regression-artifacts python3
  tests/async/test_character_mechanics_journey.py`: passed, including the
  repaired setter path and denials described above.
- `make test-all -j8 TEST_JOBS=8`: development/production/editor/tool builds
  succeeded; **728 cases passed and 2 test-integration cases failed**, with no
  timeouts or signal exits, in 654.97 seconds. Both new mechanics tests passed
  within this run. Log: `bin/tests/character-mechanics-entry-test-all.log`.
- Both failures were then repaired and their exact tests rerun successfully:
  `python3 tests/async/test_racial_shrug.py` adds the marker header to its extracted
  innate fixture; `python3 tests/async/test_root_test_harness.py` includes the new
  journey in the expected resource-intensive set and partition case. Logs:
  `bin/tests/character-mechanics-racial-shrug.log` and
  `bin/tests/character-mechanics-root-harness.log`. No further production edits
  followed the gate. The whole gate was not rerun after these test-only repairs.
- `./scripts/format.sh --check`, `git diff --check`, and discovery of both
  character-mechanics tests passed. No database gate was run; this journey's
  authority is explicitly flat-file.

### Specialization transition connections

Current slice: six additional compiled IDs bind the actual `CMD_SPECIALIZE`
function-pointer slot, race/spec predicate, selection handler, skill refresh,
snapshot capture field, and load field. Markers identify the registration,
assignment, refresh call, capture and materialization statements. The Guardian
grant depends on the selection connection. All production additions describe
existing execution; they do not change gameplay decisions or saved data.

`TransitionConnection` refers to those same IDs and existing `player_status_field`
values. It describes the permanent spec assignment, retained primary/secondary
class, race, level, experience, epics and carried coins, and refresh/capture/load
dependencies. The validator compares the live command-slot value with the bound
handler, rejects absent/duplicate transitions and overlapping changed/retained
state, and requires matching capture/load fields for changed status. Skills are
described by the real refresh action; they are not represented as fake status
fields. This remains the first transition description, not certification of
every state component or lifecycle route.

Ablation: reuse the existing native harness, command macro, handler, skill
lookup/refresh, and full-world journey. No dispatcher, alternate save format,
second eligibility evaluator or new test runner is needed. Files are the
contract pair and native owners (`interp`, `specializations`, `guild`, snapshot
capture/materialization, and the existing innate dependency), plus the existing
mechanics test/harness. Proof combines native execution, deliberate broken-source
variants, the isolated journey and affected builds/tests.

The native fixture executes the production `CMD_N` assignment, calls that slot,
checks a future `time_unspecced` denial, selects Guardian after expiry, and checks
real `update_skills` results and retained values. Room/teacher/skill cells and
dialogue/consent services are explicit fixture boundaries; actual loaded teacher,
registered skill cells and persisted skills are covered by the separate journey.
Source mutations remove each marked statement or change the loaded field.
Compiled mutations remove the actual registration or refresh call while leaving
their functions/descriptors present. Existing Bulwark mutations remain required.
The source-definition check excludes only the exact empty `update_skills` stub
in `account/pfile-stubs.c`, because that is an offline executable without skill
refresh; a mutation of that body must lose the exclusion.

Validation for these connections:

- `python3 tests/async/test_character_mechanics.py`: passed under ASan/UBSan,
  including all source and compiled mutation cases. Positive native SHA256:
  `38c24baa9ddd074d0924530811be02e9773948a2a782da6c7493e20697827b6d`.
  Log: `bin/tests/character-mechanics-transitions.log`.
- `python3 tests/async/test_specialization_eligibility.py`,
  `test_player_snapshot_capture.py`, `test_player_load_pipeline.py`, and
  `test_death_respawn_state.py`: passed (each path is under `tests/async/`).
- `make -C src -j8`, `make -j8 build-production build-editor`,
  `make -C src -j4 pfile`, and
  `make -C migrations/tools -j4 all affects pfile_converter`: passed; migration
  tools required no rebuild. Logs use `bin/tests/character-mechanics-transitions-`
  with `build`, `consumers`, `pfile`, and `migration-tools` suffixes.
- `./scripts/format.sh --check` and `git diff --check`: passed.
- `DURIS_REGRESSION_BUILD_CACHE=bin/regression-artifacts python3
  tests/async/test_character_mechanics_journey.py`: passed, including teacher
  selection, real skill rows, passive dispatch, relog and restart. Log:
  `bin/tests/character-mechanics-transitions-journey.log`; server SHA256:
  `e8feeac502021b9876fc16f8865da625c489f5b09a5eb8fef0abd211f6c0ddc8`.
  No new whole-suite or database-gate claim is made.

The transition slice is committed and pushed as `9fbec36f8`.

### Passive callback and innate dispatch connections

The next slice binds Bulwark's actual `innates_data` row, the real `CMD_INNATE`
slot and `do_innate`. A passive connection requires a null callback and a matching
effect dependency; it cannot claim completion merely because its callback is
absent. Command-entry validation now checks actual slot contents for both
specialization and innate dispatch. Exact markers cover the command assignment
and active/passive dispatch branch. Existing interpreter position/combat/aggro
policy and gameplay execution remain unchanged.

The native fixture keeps the entire production innate table unchanged. Active
callback functions are aborting fixture boundaries, while native name parsing,
eligibility, listing and dispatch run for Bulwark. Tests check the locked level-40
listing/denial and level-41 passive response without adding a timer affect.
Compiled variants remove the innate command assignment, give the passive an
active callback, or replace its dispatch message; each must fail. These checks
do not qualify the other innate effects. The existing full-world journey already
exercises real innate dispatch; its broader fixture boundaries still apply.

Outcome: connect intentional passive registration to actual command/use/effect.
Files: existing contract pair, `innates.c`, `interp.c`, and existing native
mechanics fixture. Proof: that fixture and mutations, affected innate tests,
required builds and the isolated journey. No additional callback registry or
runtime dispatch layer is introduced.

Validation:

- `python3 tests/async/test_character_mechanics.py`: passed under ASan/UBSan,
  including the new compiled mutations and retained specialization/Bulwark
  mutations. Native SHA256:
  `4677219564753914d5dcb4f120f3792779f9dafbe8093dc4b61469c9990afd51`.
- `python3 tests/async/test_innate_reflection.py` and
  `python3 tests/async/test_racial_shrug.py`: passed.
- `make -C src -j8`, `make -j8 build-production build-editor`, and
  `make -C src -j4 pfile`: passed.
- The isolated full-world mechanics journey passed again with the new callback
  and command connections. All evidence uses the
  `bin/tests/character-mechanics-passive` prefix (`.log`, `-reflection.log`,
  `-shrug.log`, `-build.log`, `-consumers.log`, `-pfile.log`, `-journey.log`).
- Formatting and whitespace checks passed. No new whole-suite or database-gate
  claim is made.

The passive slice is committed and pushed as `8733398c0`.

### Unspecialization behavior and reversal evidence

Committed behavior evidence (`a885c8611`) extends existing tests before connecting this route. The native
`test_unspecialize_guard.py` now executes both production handler and completion
with the real epic transaction and command codec. It checks unspecialized and
insufficient-funds denials; an injected invalid PID checks submission rejection.
The refusal callback is also exercised directly, without claiming that a valid
single-threaded purchase can pass the handler's funds guard and then lose its
balance before submission. Success debits exactly 10, clears the spec and invokes
refresh/forgetting before ledger enqueue. A rejected ledger queue retains the
completed in-memory change; repeating the prayer does not charge twice. Skill
refresh and spell forgetting are observed call boundaries in this native test.

The isolated game journey now goes to the loaded blood-red altar (object 12016,
room 12116), using explicit staff transfers and epic-balance fixtures (9 and 12).
It checks insufficient funds, the actual prayer/purchase, removed Shield Punch
and Bulwark, retained Guard at learned 40 / taught 70 (the base Warrior grant at
level 41), and save/restart. The existing inspector adds the saved epic balance.
This does not prove ordinary travel, earning the points, or memorized-spell
removal. The native test, extended journey and repository checks all pass.

Ablation: use the existing guard test, full-world journey and snapshot inspector;
no production behavior or new test infrastructure changes. Required proof is
native transaction ordering plus the actual altar/persistence path. Connect the
altar assignments, completion, resets and field/lifecycle dependencies next;
behavioral evidence alone does not supply those links.

Validation for this test-only slice:

- `python3 tests/async/test_unspecialize_guard.py`: passed with ASan/UBSan and
  non-recovering undefined-behavior checks.
- `python3 tests/async/test_flatfile_player_repository.py` and
  `python3 tests/async/test_epic_in_memory.py`: passed.
- `DURIS_REGRESSION_BUILD_CACHE=bin/regression-artifacts python3
  tests/async/test_character_mechanics_journey.py`: passed both selection and
  reversal journeys. It reused the unchanged verified server, SHA256
  `27c30d19f90e8b9a04a413101bd6b0f5f2265934c9981df42997d3cc901aca19`.
- Logs are `bin/tests/character-mechanics-unspecialize-{native,repository,epics,journey}.log`.
  Formatting and whitespace checks passed. Production source is unchanged in
  this slice; no redundant server build or whole-suite run was required.

### Altar registration and completion connections

Current slice connects both actual altar assignments to the object procedure,
purchase handler, native epic transaction/debit and completion, skill refresh, spell forgetting, and
spec/epic capture/materialization. It reuses `obj_proc_type`,
`epic_completion_fn`, the existing status field IDs and the existing connection
aggregate. `ObjectRegistration` retains the vnum, address of the loaded native
prototype table and native lookup function. The validator checks the current
vnum and callback, including a missing vnum whose legacy assignment fell back to
slot zero. These are read-only descriptors and compiled site markers; gameplay
handlers and ordering remain unchanged.

A transition can now name both real entries for one mutation. Its validator
follows declared dependencies to that mutation and checks each actual entry
registration. This replaces the assumption that every transition is directly
handled by a command callback. The only helper added to validation is shared by
the connection and transition checks; no gameplay dispatcher, registry or
alternate execution path is introduced.

The expanded native fixture initializes the two production assignment statements
using the real object lookup over an explicit three-prototype fixture, then
executes each altar's function slot through prayer, purchase, completion and
refresh. Real `forget_spells(-1)` selects both pending and fully memorized spell
affects while preserving an unrelated affect. Affect unlinking/event stop and
ledger enqueue are controlled fixture boundaries; the test does not certify the
generic affect/event cleanup implementation. Missing slots, missing vnums and
disconnected purchase paths must be rejected. Source and compiled variants remove
registration, the debit, completion or forgetting to prove those checks detect
breakage. The reverse scan now also accounts for the two altar vnum literals and
`unspec_altar`: a new overwrite, numeric alias or caller creates an unowned-site
diagnostic. Only the native function/prototype headers are vocabulary exclusions,
not their bodies. Wider registration history and helper/alias migration remain
open; these bounded checks are not whole-repository coverage.

That reverse scan found the existing `get_ival_from_proc` comparison in
`tradeskill.c`. It is now a connected valuation dependency of both altar entries.
The altar's comparison was separated from the existing infrastructure-object
disjunction at the same point, preserving its `-100000` contribution. The native
fixture executes the real valuation function and rejects a changed contribution;
other object callback bodies are aborting fixtures because valuation only
compares their addresses. `itemvalue` and world-reset calculations remain separate
downstream dependencies to connect.

The epic balance is materialized from `result.domains.epics`; its status-switch
case intentionally does nothing. The marker binds that real assignment. Backend
decoding into `result.domains` still needs its own connections in the wider
persistence trace; the new field connection alone does not prove that hop.

Outcome: connect the already-tested altar route and its state changes. Files:
existing contract pair, assignment/object/specialization/memorization/training
owners, snapshot capture/load, and existing native mechanics/guard fixtures.
Proof: native route and broken-source cases, affected persistence tests and
builds. The full-world behavior evidence from `a885c8611` remains applicable;
this slice changes no gameplay decisions.

The native mutation fixture now compiles unchanged translation units once per
private test run and rebuilds only the changed unit for each variant. It retains
all native sources, sanitizer flags and outcome assertions, with no cross-run
cache or edits to production files during tests.

Validation on 2026-10-14:

- `make test-all -j8 TEST_JOBS=8`: development/production/editor/tool builds
  succeeded; **729 passed and 1 fixture-integration test failed**, with no
  timeouts or signal exits, in 656.52 seconds. The mechanics native test passed
  in 32.90 seconds; its full-world selection/reversal journey passed in 143.45
  seconds. Log: `bin/tests/character-mechanics-altar-test-all.log`.
- The failure was `test_web_spray.py` extracting the newly marked `do_innate`
  body without including the marker header. The fixture now includes it, and
  `python3 tests/async/test_web_spray.py` passes its targeting, cooldown/defence,
  refresh, restoration, movement and cleanup cases. No production repair was
  needed for this failure.
- `test_root_test_harness.py` now requires discovery of the mechanics native and
  world tests plus the specialization eligibility and unspecialization guard
  tests. Its focused run passes; removing or renaming one cannot silently omit
  that evidence from the default suite.
- `make -C src -j8`, `make -j8 build-production build-editor`,
  `make -C src -j4 pfile`, and
  `make -C migrations/tools -j4 all affects pfile_converter`: passed. The last
  command found its artifacts current. Focused unspecialization, epic memory,
  snapshot capture/load, Reflection and racial-shrug tests also passed.
- The final native mechanics fixture run passed all source and compiled mutation
  cases, including explicit nonzero experience/coin retention for both altars.
  Native executable SHA256:
  `6285860c8eb158a9d2a13795e92b726e0a9b6a56e0ebf2191b5394a64a25d5c2`.
  The whole gate was not repeated after these test-only changes. No database-gate
  claim is made.
- Evidence uses the `bin/tests/character-mechanics-altar-` prefix with
  `connections`, `build`, `consumers`, `pfile`, `migration-tools`, `guard`,
  `epics`, `capture`, `load`, `reflection`, `shrug`, `web-spray`, and
  `root-harness` log suffixes. Formatting and whitespace checks pass.

### Human/Orc multiclass trace in progress

The next trace uses the actual assigned room at 52904 for normally created Human
and Orc Warriors choosing Cleric as their secondary class. The existing journey
now covers wrong location, level 49, wrong race, invalid/disallowed class,
insufficient epic balance, success, repeated selection, and restart. Boundary
levels and balances remain explicit staff fixtures. Expected behavior follows
the inspected native path: reset to level/experience 1, preserve played time,
clear spec/prestige/trophies, retain the primary class, and treat the shipped
zero-epic requirement as a threshold rather than a purchase. Secondary-only
Meditate is granted at level 6 with cap 95; primary Kick retains cap 100 and
shared Bandage takes the better cap (95). The world run passes for both races,
including normal Orc creation, the full reset and secondary skills through restart.

Outcome: connect and qualify the room/reset/secondary-class/persistence chain for
both races. Files: existing mechanics/native/world fixtures and snapshot inspector,
the shared creation helper, and the actual room/reset/skill/persistence owners as
their connections are added. Proof: native policy/reset/consumer assertions plus
the real mortal room command and persisted before/after state. Reuse existing
reset and skill code; do not add a transition executor. Guild, epic-skill refund,
spell cleanup and ordinary temple acquisition still need their specific evidence.
No change to eligibility, thresholds or balance is intended by the migration.

A separate defect was reproduced while adding this journey: `multiclass_proc`
restored `played` after `do_start` but left the new `logon`, losing elapsed time
in the current session. The real saved total fell from 20,043,221 to 20,043,201.
The extended playtime capture test also fails before the fix on the preserved
clock assertion. The procedure now restores both fields. The fixed-clock capture
test, periodic checkpoint test, server build and full-world Human/Orc journey pass.
Before-fix evidence is in
`bin/tests/character-mechanics-multiclass-before.log` and
`bin/tests/multiclass-playtime-before.log`. Keep this gameplay repair separately
scoped from the connection migration.

Post-fix evidence is in `bin/tests/multiclass-playtime-{after,checkpoint,build}.log`
and `bin/tests/character-mechanics-multiclass-journey.log`. The tested server SHA256
is `3f7c6410ba6c15efc060d3ead7ff519deb67f716fec04e6e0bb512f0c34fda4d`.
The playtime repair is committed and pushed as `e29f344b6`. The
journey/creation-helper/inspector extensions remain a separate working change.
The journey also exposed a
denial-flow defect: insufficient funds in the correct room falls through to the
generic command and incorrectly says the player is in the wrong location; race
denials were duplicated. The room now returns handled for those two denials.
The native room-plus-fallback test fails before this repair and passes after it;
the full Human/Orc journey also passes with exact denial-message assertions.
No eligibility or mutation rule changed. Logs:
`bin/tests/multiclass-denial-{before,after,build}.log` and
`bin/tests/character-mechanics-multiclass-journey.log`; latest server SHA256:
`ceb39f059f638a040bf51c10950815b3af986df2f4a796e354f47c4041f6f141`.
Native positive executable SHA256:
`be6655d2d44987824218c75e3307c9cd058e235a33d76326baf29c1f9f1fbf62`.
This message-path repair is kept separate from the playtime fix and the connection
migration. The denial repair is committed and pushed as `32d41fae9`.

The native mechanics fixture now additionally runs actual `do_start` /
`do_start_impl`, `NewbySkillSet`, `refund_epic_skills` and its completion, and
`clear_zone_trophy`. It uses the production epic reward table and real property,
racial-stat and class-HP loaders. Human/Orc assertions cover level/XP/base-stat
reset, title/prestige/trophy clearing, both time fields, guild pointer retention
with parole rank, retained flags/coins/tradeskills, and normal learned-skill reset
(including retained taught values for unavailable skills). A seeded 20-point
Epic Strength skill returns 300 epics and stages 2,000,000 copper using the native
refund logic; the epic skill is cleared while Forge remains. Both pending and
full memorization affects are selected for removal.

Guild construction/storage, kit delivery, restore presentation, coin pickup,
save requests and affect/event cleanup are explicit fixture boundaries. Skill
cells are controlled fixtures; actual initialized skill cells are checked by the
world journey. Native consumer tests cover primary, secondary-only and shared
skill requirements/caps, configured cap changes, the 5/6 grant boundary, and the
HP calculator taking the larger class modifier in both class orders. They do not
claim live level-cap progression, full guild/coin-refund persistence or ordinary
acquisition. Compiled mutations remove reset, refund, time retention, the
secondary delay or the secondary HP contribution; every variant must fail.

Validation for this behavior slice:

- `python3 tests/async/test_character_mechanics.py`: passed with ASan/UBSan and
  all retained/new mutations. Native SHA256:
  `c7a485667006059658d94b65e21a26173ca1682f0d0873770cb0cfce5bab1035`.
- `DURIS_REGRESSION_BUILD_CACHE=bin/regression-artifacts python3
  tests/async/test_character_mechanics_journey.py`: passed the complete
  specialization and Human/Orc multiclass cases with the server identified above.
- The shared creation helper handles actual alignment/hometown/automatic-town
  prompts and adds only the race selector needed by Orc creation. The existing
  `test_flatfile_newbie_regrant_journey.py` also passed all Warrior/Sorcerer cases
  with Chaos off and on. Its concurrent observer's maximum response was 0.250s.
- `python3 tests/async/test_flatfile_player_repository.py`: passed. The inspector
  exposes played time, prestige, guild fields and trophy count, and preserves
  signed values (including the `-1` epic denial fixture) when printing JSON.
- Logs use `bin/tests/character-mechanics-multiclass-{native,journey,helper,inspector}.log`.
  These are focused results, not a new whole-suite/database gate.

The behavior baseline is committed and pushed as `6f471558a`.

### Multiclass connections in progress

The compiled contract now connects the listing command, actual room assignments
(17 and 52904), the native selection predicate and mutation, reset/skill setup,
restore, forgetting, epic refund/completion, trophy clearing, skill lookup/cap
properties, and HP/racial-Con inputs. Room 17 remains explicitly unresolved for
ordinary mortal access. Existing handlers still execute the transition.

The two record shapes remain. A room binding uses the live table, vnum and native
lookup, as object bindings do. Related multiclass status fields use a read-only
span of existing `player_status_field` IDs. Status, skills, affects and trophies
use the native checkpoint-component enum; transition validation requires their
capture and load links. The whole status component includes text (such as title),
conditions and quest values alongside the explicitly named integer fields. The
specialization transitions also name their changed status/skill/affect components.
Exact markers bind every member of a grouped status link;
removing one member cannot be hidden by the other markers. Collection markers
name the actual capture statements and materialization loops, without swallowing
new code inside those loops.

The native fixture initializes both production room assignments with real lookup,
checks removal of each registration, and executes the assigned function slots.
It rejects missing status members and mismatched collection load links. Native
output now reports whether a binding is callable or data, derived from its C++
type; the source check no longer mistakes native component constants for function
names. New source/compiled mutations cover room overwrite/caller/alias, command
or room registration removal, status capture removal/wrong source field, and
collection load removal. Existing reset/refund/clock/skill/HP mutations remain.

Review corrected the transition's wallet description: a failed coin-pickup stage
can use the existing direct-wallet fallback, so the carried denominations are
conditionally changed, not unconditionally retained. They now have native
capture/domain-materialization links. The fixture links the real currency
transaction and codec, and tests staged pickup, successful direct credit, and
credit refusal at the wallet limit. Refusal preserves the wallet while retaining
the completed epic refund/skill reset and its existing staff-contact message.
Account identity, bank/writer services and pickup storage remain fixture
boundaries. A compiled missing-credit mutation must fail the wallet assertion.

Ablation: extend the existing typed records and fixtures; reuse native field and
component IDs instead of inventing persistence state or a transition runner.
Files are the contract pair and existing command, room, reset, skill/stat, refund,
trophy and capture/load owners, plus the existing tests. Proof is the native
route/consumer/mutation suite, focused persistence tests, builds, and the existing
isolated journey. The final focused native run, including all structural/reverse
and executable mutations, passed with SHA256
`b275c6003daaa286afd18164cf2548c53b5689f008baa0215e572b0890a9e95a`.
Development/production/editor/pfile/migration-tool builds and focused playtime,
snapshot capture/load and currency tests passed. The full `make test-all -j8
TEST_JOBS=8` gate finished with **728 passed, 2 failed**, no timeouts or signal
exits, in 740.38 seconds. The failures were fixture integration: the memorized
spell test omitted the marker header from extracted `SKILL_DATA_ALL`, and the
temple's loaded ice golem put the Orc into combat before selection. The spell
fixture now includes the header and its focused run passes. The journey now
purges only the temple guardian before transport and returns characters to their
saved creation rooms before restart; its focused rerun passed all specialization,
reversal and Human/Orc multiclass cases. This is
explicit handler/persistence setup, not temple-acquisition or encounter proof.
Evidence is under
`bin/tests/character-mechanics-multiclass-connections-*.log` (native output uses
`character-mechanics-multiclass-connections.log`). The exact failed spell fixture
and revised journey were rerun successfully; the whole gate was not repeated
after these test-only repairs. The final journey server SHA256 is
`90526f6acb3e780937c873eb600092bbafb96ee9a98879d20c25cc615ab3e2f0`.
The native mechanics test also passed within the full gate (86.54 seconds).
No production changes followed that gate. Kit delivery, broader backend and
cleanup dependencies, full acquisition and remaining option families still need
their separate connections/proof; no complete-trace or whole-issue claim is made.

### Revenant lifecycle investigation

The world fixture extends a normally created Orc with a staff-supplied crown
(22070) and level 41, then exercises real wear/periodic application, save/restart,
and removal. The inspector exposes birth time and saved affect rows. The focused
`--trace revenant` case starts from a single-class Warrior; the default full
journey applies the same case after the Orc's Warrior/Cleric multiclass story.
This is an item-handler/persistence fixture, not acquisition from the crown's
world holder. Starter equipment is dropped after restart to allow crown removal
within the form's inventory limit.

Outcome: qualify and connect application, scheduled retention/reversal, generic
affect removal, death and checkpoint/reload without losing the original identity.
Files are the existing native/world mechanics fixtures, snapshot inspector and
actual item/event/affect/persistence owners. Proof must include observable race
and age behavior, not just a registered callback. No storage-model replacement
or enablement of legacy routes is authorized by this investigation.

Additional source evidence: the active crown and unbound old Dragonlord body are
the `TAG_RACE_CHANGE` producers using NOSAVE; both change birth time and reset it
to the original race's base age on reversal. Yzar and Shaboath tags are saveable
and have different lifecycles. A fix must preserve that distinction. Revenant
base age is 100 versus Orc base/max ages 15/80, so race-only normalization could
produce an invalid old-age combination. `age()` additionally adds five years and
the current race's base age; this repair preserves existing reversal birth-date
semantics, rather than recovering the pre-transformation age (which is not stored).

**Reproduced defect, separately scoped repair:** the saved checkpoint had race 19
and no race-change tag. After a clean private-server restart, crown removal
succeeded but the character remained Revenant throughout the 90-second reversal
window. Log: `bin/tests/character-mechanics-revenant-before.log`. The new native
capture regression also failed on the original-race assertion before the repair
(`character-mechanics-revenant-capture-before.log`).

The repair reuses capture's cycle-aware affect traversal. For a NOSAVE
`TAG_RACE_CHANGE`, it projects the original race and the existing removal
birth-date policy into the snapshot, including status-only saves. Live race,
birth and affects remain unchanged. Saveable Yzar/Shaboath tags and unrelated
NOSAVE affects keep their behavior. Invalid original-race indices reject capture
before table access, and a failed capture does not publish a partial snapshot.
This prevents new identity loss; an already-written snapshot missing its original
race cannot be repaired by inferring that race. No existing player data is edited.
No schema change, generic transformation framework, or activation of old
Dragonlord is needed. The existing capture test executes the real capture and
codec against the real racial table; playtime and locker fixtures now link that
table as well. The native capture, playtime, locker and load regressions pass.
The connected-mechanics sanitizer/mutation test also passes (native SHA256
`fc135c4bd4063b40f88fb85eaa7dd410d7dd31d60994f252c3c9416a551f853c`).
Development, production, editor, pfile and maintained migration-tool builds pass.
The focused private-world retest passes: a checkpoint retains the base race and
omits the temporary tag while the live character stays Revenant; restart
reapplies the worn crown, and removal restores Orc and the normal reversal birth
date. Server SHA256:
`a6dab7ab96e4b3f04c970e5925b0e7280f7ac64c7e50109096ac294d128713f2`.
Logs use `bin/tests/character-mechanics-revenant-` with `capture`, `playtime`,
`locker`, `load`, `native`, `build`, `consumers`, `pfile`, `migration-tools` and
`journey` suffixes. Formatting, whitespace and all 57 local plan links pass.
The full `make test-all -j8 TEST_JOBS=8` gate passed: **730 passed, 0 failed**,
no timeouts or signal exits, in **668.07 seconds**. This includes the default
journey's combined specialization, Human/Orc multiclass and crown case, which
passed in 264.60 seconds. Log:
`bin/tests/character-mechanics-revenant-test-all.log`. No source changes followed
the gate. The separate Docker/database gate was not run; persisted world evidence
for this repair is flat-file, with shared capture/codec execution in the native
regression. The Revenant structural connections and remaining acceptance scope
are still incomplete.

Repair checkpoint: `1fd3d4744`, published before upstream integration.
Current slice: add Revenant connections beside its actual object assignment,
periodic dispatch, application/reversal callbacks and race/birth/item capture/load
statements. Outcome is a checked callback/transition chain with explicit state and
persisted equipment dependencies. Files are the existing contract, item/world and
persistence owners, plus the native mechanics fixture. Proof combines native
handler cases, missing-registration/consumer/capture mutations, the existing
world journey and affected builds. Keep gameplay rules and the save schema;
reuse native pointer types, tables and the existing observer instead of adding a
dispatcher or another rules store. The world test supplies restart/removal
evidence, but death and conflicting-form behavior still need their own cases.
Individual teacher/timer guards, creation, remaining persistence dependencies,
real HP damage and complete coverage of all three initial traces remain open.
The successful journey does not replace missing structural links. Ordinary
travel, live progression caps and the broader acceptance matrix remain open.
No completion or review-ready claim is made for the whole issue.

Read-only leads for the next Revenant trace: object 22070 is defined in
`areas/obj/cerebusp.obj`, and the selected world gives it to Haratius Drakenstone
(mobile 142425, room 142446) in `areas/zon/Voluntown.zon`. The assigned
`revenant_helm` runs on a worn item's periodic call, strips other equipment,
adds `TAG_RACE_CHANGE` with the original race and `AFFTYPE_NOSAVE`, changes race
and birth time, and schedules `event_revenant_crown`. The event retains the form
while the crown is on the head; otherwise it restores race, resets birth time to
the race's base age, removes the affect and strips equipment. Generic
`affect_remove` also restores the saved race, and the fatal-damage path restores
race before death handling. The original capture saved `GET_RACE` while omitting
NOSAVE affects; the reproduced restart failure and repair are recorded above.
The connection slice below binds application/reversal; actual death, authentic
conflicting-form entry and other lifecycle paths still need their own evidence.
These source leads do not prove those paths or ordinary acquisition.

### Revenant registration, callback and persistence connections

Thirteen new compiled IDs bind the crown's actual object slot, periodic dispatch,
application, retention/reversal callback, valuation, race/birth capture and load,
NOSAVE projection, equipment/inventory capture and load, and the native racial
age table. The observer accepts the existing `event_func_type` and a typed pointer
to the existing racial table; it does not invoke gameplay. The temporary
transition declares race/birth changes, retained class/spec/level/XP/epics, and
status/affect/equipment/inventory components. Existing validation requires their
capture/load links and an actual registered route to the mutation.

Exact markers bind the existing statements, including the periodic-enrollment
guard in `read_object`, dispatch through the assigned slot, retained original
race and NOSAVE flags, event scheduling, restoration, and field/item attachment.
The reverse check now includes crown vnum/procedure/event symbols. Llyren's
artifact locator has one exact exclusion: its rareload display filter makes no
character identity or admission decision. Changing that filter loses the
exclusion; it cannot absorb other branches. Wider race-symbol/helper/registration
history coverage remains open.

The native fixture runs the real crown and periodic callbacks, checks unworn,
wrong-command, dead/NPC and existing-tag guards, original-race/tag flags, birth
dates against the real table, other-equipment stripping, retained identity,
reapplication prevention, worn retention, removal, wrong-race damage/wait, and
missing-tag reporting. Scheduling, equipment transfer and affect allocation/
unlinking are explicit fixture services. It does not claim actual scheduler
execution, generic affect cleanup, removal-procedure death or fatal damage.
Those boundaries matter: the unlink fixture does not restore race, so removing
the crown callback's race restoration really fails its independent assertion.
The full-world journey remains the actual enrollment/scheduler/restart proof.

Source mutations remove attachment/capture/load statements, change load fields
or callback guards and the exact locator exclusion, and introduce new crown
aliases, overwrites and callers. Compiled variants remove registration, dispatch,
scheduling or restoration, lose the original race, and alter the Orc base-age
row. All older mutation cases remain required. The complete native sanitizer and
mutation test passes; positive executable SHA256:
`639fb45f1be937ac4fc04963b0804804323b89153ab7d5b8edf333f91aeef366`.
Development, production, editor, pfile and maintained migration-tool builds pass,
as do capture, load-pipeline and item-materialization tests. Logs use
`bin/tests/character-mechanics-revenant-connections` (native) and the `-build`,
`-consumers`, `-pfile`, `-migration-tools`, `-capture`, `-load` and `-items` suffixes.
Formatting and whitespace checks pass. The full gate finished with **727 passed,
3 failed**, no timeout or signal exits, in **689.96 seconds**. The mechanics world
journey passed in 268.28 seconds and the upstream flight evidence fix passed in
421.08 seconds. Log: `bin/tests/character-mechanics-revenant-connections-test-all.log`.
All three failures were then repaired and their exact tests passed individually:
the periodic rearm and newbie object-template extracted-code fixtures now include
the marker header, and `e3a0b5b09` separately fixes the documentation checker's
incorrect collapsing of adjacent spaces in heading anchors (including a new
spacing/duplicate-anchor case). The existing documentation link was valid and
was preserved. Logs have `-periodic`, `-template` and `-documentation` suffixes.
No production changes followed the gate, and the whole gate was not repeated
after these test-only repairs. The death-age defect below remains unresolved;
these results do not complete the Revenant lifecycle or the overall plan.

**Next separate defect repair: death cleanup retains the form's birth date.**
A private normal-Orc/crown probe used the real staff bare-hand `kill` command
(`do_kill` → `die`; this is not the normal fatal-`raw_damage` path). The terminal
snapshot restored race 13 and removed `TAG_RACE_CHANGE`, but retained birth
`1684838011`, versus the normal-removal checkpoint projection `1775873017`.
That is approximately 85 MUD years of extra age. The game returned the player to
the account menu and persisted the terminal snapshot; the assertion comparing
death and normal-removal birth policies failed. Evidence:
`bin/tests/character-mechanics-revenant-death-before.log`. The isolated probe is
`bin/tests/revenant-death-probe.py`, adapting the existing focused world journey
without changing maintained source. The shared game was untouched.

Source path: `die` removes non-permanent affects before terminal capture;
`affect_remove` restores the tag's original race but does not restore birth.
By then the tag is gone, so checkpoint projection cannot normalize it. Repair
this cleanup in a separately scoped gameplay commit, preserve saveable race-change
semantics, and add native plus actual death/restart evidence. Also qualify normal
combat death and the generic cleanup connection. Do not mark this lifecycle
complete merely because the registered callback/removal tests pass.

Continuation finding: `epic_transaction_submit_identified` currently changes
the authoritative in-memory epic balance and calls its completion **before
returning**, then queues the ledger row. An unspecialize purchase must therefore
be tested against that current ordering. A rejected ledger enqueue does not
roll back a completed purchase; insufficient funds and invalid submit inputs
have different outcomes. Reuse `test_epic_in_memory.py` and
`test_unspecialize_guard.py` rather than assuming an asynchronous purchase.
The actual altar assignments are objects 2203 and 12016; their world resets put
them in rooms 2263 and 12116. These locations do not prove ordinary travel.
The native object callback type is the existing `obj_proc_type`; both slots are
assigned in `specs.assign.c`. `unspec_altar` handles `CMD_PRAY` for a living PC
when the argument contains `altar`, then invokes `unspecialize`. `CMD_PRAY` also
has a normal `do_memorize` command-table fallback, so do not misdescribe the
altar as that command's direct handler. The altar connections above use their
real object slots and purchase/completion path. A prototype binding retains
the expected vnum: `real_object0` returns slot zero when a vnum is absent, so
pointer presence alone cannot establish the intended object's registration.

Entry-route source findings:

- `interp.c` assigns `CMD_SPECIALIZE` to `do_specialize` through `CMD_N` with
  `STAT_SLEEPING + POS_PRONE`, level 0, and no aggro check. Connect the actual
  registration, not just the handler's existence.
- The handler checks teacher presence, PC identity, teacher class, existing
  specialization, `time_unspecced`, level 30, and the race/spec allowance before
  assigning `player.spec`, calling `update_skills`, and sending the teacher's
  success message. Teacher search uses `GET_CLASS`, but the subsequent non-Dragoon
  check also requires exact primary-class equality; retain both decisions.
- Read-only inspection of generated world data found loaded pure-Warrior teachers
  with `ACT_SPEC_TEACHER`: Arian (mobile 9432, reset room 9725 in Sarmiz), Rethorn
  (42939, room 42934 in Raxthan), and Ugort (83229, room 83134 in Alatorin), among
  others. Their areas are selected by `areas/AREA`. These are acquisition leads,
  **not** proof of mortal travel, teacher interaction, or ordinary reachability.
- Reuse the full-world setup in `run_world_quest_dual_backend.setup_run_root`,
  the existing clients/build-artifact helper, and disposable authority. The
  recovery `IsolatedServer` always boots with `--minimal`; it cannot by itself
  establish full-world teacher acquisition. The planned new
  `test_character_mechanics_journey.py` is the current implementation above. Any staff level,
  transport, or equipment setup must remain explicit fixture scope.

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
2. Extend the bounded reverse check from its migrated Bulwark/altar sites to every
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
At the foundation checkpoint the reverse check was still absent; the later slices
above add it for a limited set of sites. Exhaustive classification remains open.

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
  guards and the real completion with the native epic debit/ledger ordering;
  refresh and spell forgetting are observed call boundaries. The mechanics
  fixture additionally runs real refresh/forget selection with controlled affect
  removal, and the world journey checks the loaded altar and persisted results.
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
