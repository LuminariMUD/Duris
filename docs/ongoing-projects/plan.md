# Character mechanics: delivery plan

Updated 2026-10-19. Tracking: [issue #52](https://github.com/LuminariMUD/Duris/issues/52).
Branch: `feature/52-character-mechanics`. Implementation is **paused and incomplete**
at the user's request. Resume from the checkpoint below.
This revision replaces the accumulated checkpoints and the one-connection-at-a-time
sequence. It changes the delivery method, not the required scope. Historical
implementation detail remains in Git; fixed defects are in
[REGRESSIONS.md](../testing/REGRESSIONS.md).

## Outcome, non-goals, files, and proof

**Outcome:** a small compiled C++ contract makes every race, class, specialization,
ordered multiclass pair, ascension/descension route, and permanent or temporary
transformation traceable in both directions:

```text
option <-> entry/eligibility <-> grants/effects/restrictions
       <-> progression/mutation/commit/failure
       <-> resulting state/reversal/save/load <-> named evidence
```

Every scoped gameplay site has a connection, a shared dependency, or a precise
reviewed exclusion. Disabled and unbound legacy routes remain visible. Disguise,
control transfer, affect forms, and world/item routes are in scope. An index of
functions alone is insufficient.

**Non-goals:** balance changes, enabling disabled routes, storage changes, or
moving all mechanics into one module. No JSON catalogue, exporter, new service,
registry database, rules engine, generic dispatcher, general C++ parser, or new
test framework. Gameplay defects require separate changes. The user requested a
minimal documented checkpoint and branch push; release operations remain separate.

**Files:** finish the existing [contract header](../../src/player/character_mechanics.h)
and [implementation](../../src/player/character_mechanics.c), connections beside
existing owners, and existing tests. Use
[test_character_mechanics.py](../../tests/async/test_character_mechanics.py), its
[native harness](../../tests/async/character_mechanics_harness.cpp),
[test_character_mechanics_journey.py](../../tests/async/test_character_mechanics_journey.py),
[test_creation_prompt_journey.py](../../tests/async/test_creation_prompt_journey.py),
and relevant existing regressions. Keep the work queue here; no additional
planning or evidence catalogue is needed.

**Proof:** compiled forward validation; complete reverse site accounting with
mutation checks; native behavior assertions; real command/world and persistence
journeys. Keep these evidence scopes distinct. Structural coverage is exhaustive;
behavioral claims name the assertions actually exercised. Required family and
lifecycle cases below cannot be replaced by an “unverified” label.

Normal fixtures explicitly disable `CHAOS_MUD`, `CREATION_ALL_RACES`, and
`CREATION_ALL_CLASSES`, even when inherited settings enable them. Use committed
[creation settings](../../lib/creation_availability.cfg),
[properties](../../lib/duris.properties), and [world selection](../../areas/AREA).
Record backend, admission/invitation, faction/alignment, live side-cap/timer state,
level, equipment, and world conditions separately. Creation switches do not become
restrictions on existing characters. Staff setup does not prove ordinary acquisition.
Use private fixtures without `.env`; another session may use the shared dev game.
Do not stop or modify that game, its database, or Redis.

## Upstream sync, 2026-10-19

Final publication refresh also merges master `fcb54a1d068015f7ab3887944ba8929208568c0d` (October 19 player news). This follow-up changes only the news content and this note; the validated source, test, world and OpenSpec trees are unchanged. The news reload regression passes on both SQL and flat-file builds.

Merged master `f1c21a92f79d0bf429d5e241c2b890dce27e342d` without changing the paused feature scope. Preserve the item-restriction checkpoint and first-work-on-resume instructions below. Master now supplies the Hatred watcher/lifecycle repair, retained-item capture, Holy Sacrifice limits, object-template updates and weight propagation fixes. The older Hatred implementation and mutation descriptions below are historical; the focused upstream Hatred regression owns current watcher/effect behavior. Conflict resolution retains the mechanics bindings alongside the newer production behavior.

Sync validation passed: `make -C src -j8`, 16 focused regressions covering the
conflicting gameplay/persistence paths, the full existing character-mechanics
native/source/mutation regression, formatting, documentation, and whitespace.
The initial isolated world run passed disabled transformations, Phantom state,
specialization/reversal, Human/Orc multiclass persistence, and Revenant reversal
and staff death. Its remaining combat-death setup exposed an obsolete attempt
to duplicate the artifact crown. The fixture now recovers the original crown
from the character's persisted corpse; the focused Revenant rerun passed both
death modes, restart and resurrection. All 15 creation journeys then passed,
including WebSocket/Telnet and rejection/quit paths.

Logs are under `bin/analysis/branch-sync-20261019/`. This is integration evidence
for the existing checkpoint; the missing item-restriction cases below remain
unfinished. The full regression/database burn-in and MariaDB gameplay journeys
were not run. No shared game, database or Redis service was changed.

## Current checkpoint

**Pause handoff (2026-10-14):** preserve the unfinished shared item-restriction batch
on this branch. It adds typed bindings for `obj_race_bit_set`, `can_char_use_item`
and `can_prime_class_use_item`, four mask-call markers and eight consumer markers
across creation kits, wearing, NPC equipment, auction information, object/world
procedures and necroplasm. The observer's source checker now recognizes these
shared call sites. The only predicate-body reshaping is an equivalent braced `else`
to attach a marker; no item policy or balance change is intended.

This is a **WIP checkpoint, not a completed restriction batch**. Class,
specialization, secondary-class, NPC-image and body/wear behavior assertions are
still missing from the new bindings. New item-specific alias/caller/detached-marker
negative cases are also pending. The existing race-bit test now includes the
contract header so its extracted native predicates compile with the markers.
Pause checks passed: `make -C src -j8`, the existing race-bit runtime test, native
positive/binding assertions, current source locations, formatting, whitespace and
documentation checks. Logs are `bin/tests/character-mechanics-pause-*.log`.
At the pause, no full mutation/world/integration rerun was
claimed for these draft item changes; prior evidence below retains its recorded scope.

No PR has been opened. PR splitting was stopped before branch or PR changes when
the user requested this pause. All implementation remains in this worktree and on
`feature/52-character-mechanics`; no shared dev server, database or Redis was changed.
On resumption, own commits/tests/pushes and focused PR creation as each chunk is
ready, stacking dependencies instead of accumulating the entire project into one PR.

**First work on resume:** finish the item batch in the existing native harness,
using real primary/secondary/spec predicates; qualify all current shared callers
and the new reverse-marker rules. Preserve the general predicate's existing
class-sharing exceptions and the primary-only predicate's narrower behavior.
Then continue body/wear/mount and progression owners. The existing race-bit test
does not establish every class/specialization/body rule. Open a focused PR once
this chunk is ready; the full issue and final integration gate remain unfinished.

Implementation checkpoints pushed: `6060b7e86` fixes hatred traversal/bounds;
`b8cbf9678` connects shared innate timer/affect lifecycle ownership;
`41714f500` fixes phantasmal removal lifetime. Earlier passing batches are
`2fe7f8d72` (disabled routes),
`c926e427b` (commands), `4a11e79f6` (creation), `1abfef484` (ability tables), and
`ff80bae30` (generic race/death cleanup). The 2026-10-14 branch sync integrates
upstream `67ca142ff` after the earlier `0e27ef1e8` baseline. This brings in #72
(deferred epic tasks), #69 (epic awards at every level), and #76 (persistence
failure diagnostics). Epic skill training retains its separate level requirement.
Character-mechanics implementation remains paused and incomplete; this sync only
updates its upstream baseline.

The shared-owner batch connects innate property/cooldown, real affect application
and short-event expiry, and the affect-only phantasmal transition. The native
fixture now executes `affect_to_char` and `event_short_affect`, replacing the old
allocation stub. Phantom level 19/20, timer duration/default/override, remaining
uses, flag application, liveness/expiry, cooldown denial/reuse and shared death
cleanup pass. Derived-stat recalculation and scheduler delivery remain boundaries
of that fixture. Source validation excludes only the exact empty offline pfile
`update_skills` and `event_short_affect` stubs; real bodies must resolve uniquely.
The full native run and all seven compiled mutations passed. Final readiness
bindings and the status-field guard were then checked with the same native
positive/malformed-view assertions and current source locations; unchanged
behavior mutations were reused. The private-world persistence rerun passed.
Its inventory assertion caught an overbroad fixture reset: purging all
affects erased achievement progress and awarded another satchel at login. The
fixture now removes only the innate timer, retaining unrelated achievement state,
and compares UIDs/ownership independently of serialization order. No gameplay fix
was needed for this fixture mismatch. `--trace innate` proves live flag toggle,
cooldown denial, quit/relog and save/restart retain the form/timer, identity and
item UIDs/ownership. Staff supplies Phantom race and level; original faction is
retained. Natural Phantom acquisition and natural scheduler delivery remain
separate. World binary SHA256:
`264276e854fc350d0eee416b9433098999941106ec724d14fb10705cfbf3c1bc`.

Native/build/format/documentation/source checks passed in `innate-*.log` (the final
native binding assertions are `innate-bindings.log`, and current source locations
are `innate-source.log`). The ASan/UBSan event-cancellation test also passed;
`extract_char`'s common disarm caller is present but still needs its own reverse
connection. Affect-only transitions may omit changed status fields; transitions
claiming the status component still reject a missing status-field declaration.

**Completed repair:** `event_hatred_check` accessed released nodes after bulk removal
and scanned index `MAX_HATRED`, outside the native row. Both were reproduced
independently with ASan/UBSan. The separate fix removes one affect at a
time, emits its message before release and observes the native race-row sentinel
and bound. The existing fixture checks both pulse modifiers, refresh/no stacking,
unrelated-affect retention, one wear-off message and rearm. Native positive and
current reverse-location checks, both reintroduced defect variants, server build,
formatting and documentation passed (`hatred-*.log`; original repro is
`hatred-before.log`). The seven unchanged behavior mutations retain their passing
innate-batch evidence; the maintained default runner now includes all nine.

| Connected scope | Current evidence and boundary |
| --- | --- |
| Native identity, creation and ordered-pair tables | Exhaustive finite traversal and typed predicate checks pass. Traversal proves safety/consistency, not independent policy correctness for every cell. |
| Skill/spell/tag and innate tables | 8,807 skill/definition writes and 447 innate grants at 3,390 native caller locations; final-cell/provenance/conflict checks and new alias/caller/stale-call mutations pass. All 632 spell/poison callback symbols resolve to production implementations; effect coverage remains separate. |
| Command vocabulary/slots | 845 writes with native IDs, handlers and every guard field; combined registration coverage is 4,235 locations. All 437 command callbacks resolve independently in both backend source arms, including overloads/ACMD. Handler/guard/conflict and unobserved-write cases pass. Unexercised bodies abort in the fixture. |
| Both creation transports and account admission | All 15 private-server scenarios pass: normal menus/forbidden submissions, good-side commit/opposite-side cooldown denial, starter skills, save/restart/Telnet relog. Human Necromancer remains accepted by Telnet but listed/rejected by WebSocket's faction-derived alignment. Complete initialization state/body/innate-bit and starter-kit lifecycle ownership remains open. |
| Specialization, unspecialization, Human/Orc multiclass, Revenant and cleanup | Existing native/world/persistence cases pass at their recorded inputs. Crown normal removal, death and restart restore base race/birth. Natural teacher/altar/temple/crown acquisition and complete broader consumer coverage remain open. Bulwark still has a recording raw-damage boundary; actual HP proof is required. |
| Disabled transformations | Actual registered ascend, opposing Theurgist NPC gate, wrong-class/49/50 descend and corpseform callbacks preserve full native character/PC/corpse state and queue no save/ledger. Private full-world mortal ascend/descend and saved-state checks pass. Legacy descend is unregistered. Downstream conversion branch/target/state declarations and successful completion behavior remain incomplete. |
| Phantasmal removal repair | Real callback/message/removal passes; restoring the old released-node read fails ASan. Missing-affect case passes. See [REGRESSIONS.md](../testing/REGRESSIONS.md#phantasmal-form-removal-message-lifetime). |
| Live progression | `with_disposable_mariadb.sh python3 tests/async/run_level_cap_mysql.py` passed against its private database: qualifying frags, thresholds/config changes, side/timer/circle unlocks, persistence and rerunnable ally-count migration. Contract ownership and character level/grant journeys still need connection. |

One precise existing conflict stays incomplete: blindfighting's Rogue Assassin
cap 100 is overwritten by the later class-wide cap 90. The native test requires
exactly that diagnostic and both original values. Preserve current behavior
pending a balance decision; final-table order alone does not establish intent.

Focused evidence lives under `bin/tests/character-mechanics-`: `creation-native.log`,
`creation-prompts.log`, `creation-build.log`, `command-native.log`,
`command-build.log`, `disabled-native.log`, `disabled-world.log`,
`phantasmal-native.log`, `phantasmal-build.log`, `progression-mysql.log`, and the
current `innate-*.log`. The corresponding formatter/documentation logs passed for
committed batches. Editor, pfile and migration tools passed at `1abfef484`; the
final gate still checks their current shared headers. The shared dev game is untouched.

The wider reverse inventory, other consumers and transitions, natural acquisition,
and required family/lifecycle cases remain open. The candidate scan is input, not
classified coverage. Continue the owner groups below; do not substitute additional
polishing of these traces for the remaining migration. The reference describes
[current bindings and evidence boundaries](../reference/CHARACTER_MECHANICS.md).

Last full repository gate predates these batches: **729 passed, 1 failed**, 669.44
seconds (`bin/tests/character-mechanics-revenant-death-test-all.log`). The sole
`test_web_spray.py` fixture dependency was repaired and its focused rerun passed;
that does not turn the earlier aggregate result green. Run the final gate at the
completed candidate, not at every metadata checkpoint.

## Shortest implementation sequence

Work through these four batches. Each batch closes
an owner group and its focused checks; do not keep polishing the three examples
while the rest of the source remains unclassified. Update this checkpoint in
place rather than appending another history section.

### 1. Close pending work and enumerate the complete scope

The pending cleanup fixture is repaired and committed in `ff80bae30`. Reuse its
passing checks and preserve the existing cleanup semantics and caller order.
The native grant tables and registration calls are now covered as recorded above.

Continue extending the existing reverse checker across maintained `src/` files and
headers. Use existing identity tables/definitions and initialized registrations
as inputs. Classify candidates by the owner groups below, including indirect
helper callers, aliases, direct identity writes, form flags, disguise/control
state, and command/object/mobile/room assignments. A token count is not the
inventory. Follow ability grants to implementations even when those functions
contain no race/class literal.

The test should report outstanding locations grouped by owner during migration.
Keep that generated diagnostic under `bin/`, not as another hand-maintained roster.
Temporary unclassified sites remain failing migration work; final acceptance
requires zero. Unsupported source forms report a location for review. Do not
silently skip them or build a parser to avoid examining a concrete site.

**Exit:** pending cleanup checks pass; every source family below is enumerated;
the remaining queue consists of concrete sites, not “finish step 1.” Do not wait
for every pilot's remaining world scenario before moving to the broad migration.

### 2. Connect tables and consumers in owner groups

Keep the existing `MechanicConnection` and `TransitionConnection` record shapes
and native typed symbol/table references. The contract observes gameplay; it owns
no formulas and never dispatches an attack or transition. Bind whole existing tables
through their real IDs and dimensions. Record provenance at existing registration
functions/macros (`SPELL_CREATE`, `SKILL_CREATE`, `*_ADD`, `ADD_*_INNATE`) once,
rather than handwriting a descriptor/test for every grant cell. Observe writes
before overwrites disappear; identify intentional precedence without changing it.
Keep the `_DE_` and `_PFILE_` consumers valid.
Bind actual command/procedure slots with their IDs/vnums and lookup, not a handler
pointer alone: `real_object0` can fall back to slot zero when the vnum is missing.

| Owner group, in order | Connections to complete and source facts to preserve |
| --- | --- |
| Identities and creation: `defines.h`, `common.c`, `constant.c`, `creation_availability_config.c`, `nanny.c`, `ws_handlers.c` | Derive races/classes/spec slots/ordered pairs from native tables, including unused specs, legacy classes, restricted and out-of-player-range forms. Class masks differ from indices; specs are `(primary class, slot)`, slot 0 is unspecialized, and Rogue Assassin differs from standalone Assassin. Bind both creation transports, admission, roster/configuration/legal-cell/alignment decisions, starter state and persistence. Missing creation switches default enabled; committed Dragoon is disabled. Preserve `class_table`'s NPC consumer in `random.mob.c`. Telnet neutral/table codes 2/3/4 and WebSocket faction alignment differ; characterize Human Necromancer instead of silently normalizing them. |
| Grants and acquisition/use: `skills.c`, `innates.c`, `specializations.c`, `guild.c`, `memorize.c`, `epic_skills.c`, `interp.c` | Enumerate actual grant structures, levels/circles/caps, callbacks and command slots. Connect teacher/race/class/slot/timer guards, training/practice, memorization, epic costs/prerequisites/completion, and unspecialization. Active innates need dispatch/cooldown/effect; passives need actual consumers. `GET_CLASS` includes secondary class; `GET_SPEC` tests primary class and slot. Effective innate race handles disguise/corpseform. |
| Effects and restrictions: `fight.c`, `dam_mods.c`, `db.c`, `affects.c`, `utility.c`, `limits.c`, `handler.c`, `actobj.c`, `mount.c` and class owners | Connect selectors to effects and property loaders/defaults for damage, casting, racial stats, HP/vitality/age, body, wear/mount and item restrictions. Secondary skills have a +5 requirement and separate caps; multiclass HP takes the larger class modifier. Equipment can replace racial stat factors. Include conditional `racewar_stat_mods.c` and all shared-trait consumers. Blood Tithe in `paladins.c` needs charging, decay, group consumers and login rescheduling, not only its spell callback. Preserve combination/order. |
| Multiclass and progression: `actoth.c`, `specs.room.c`, `actwiz.c`, `world/epic.c`, `frag_cap_config.c`, `limits.c`, `sql.c`, `maintenance_repository.c` | Reuse the existing Human/Orc connections; finish reset, guild, trophy, refund and secondary consumers. Preserve ordered eligibility, list/room fallback levels 41/50, threshold rather than debit, and reset before secondary assignment. Connect side caps, qualifying frags, timers, Hardcore, level and spell-circle unlocks. The client-free SQL cap is a floor fixture, not evidence of live cap maintenance. |

A shared rule has one connection referenced by all real consumers. Add native
binding types only when an actual remaining owner requires them. Retain exact
selector/effect sites for embedded rules; a file/function tag cannot absorb new
branches. Factor repeated source-check patterns by existing syntax where useful,
but do not duplicate entire formulas in regexes as a second behavior oracle.
Production code and native assertions supply the decision/effect evidence.
Extract a rule only if a required check needs a callable boundary that does not
already exist; preserve messages, return values, side effects and ordering.

**Exit:** these groups have no unclassified sites; every grant reaches acquisition,
use/effect or a specific implementation gap; registration conflicts and removed
bindings are diagnosed. Focused characterization accompanies moved/extracted code.
The three initial traces reuse these shared connections instead of growing a
parallel set of special-case machinery.

### 3. Finish transition families and required behavior

Use one route identity linking actual entry, eligibility, mutation, transaction
completion/failure, recalculation, cleanup and persistence. Reuse handlers/events
and [capture](../../src/player/player_snapshot_capture.c)/
[load](../../src/player/player_load_materialize.c); add no saved option object.
Describe changed and retained identity/form, class/spec, level/XP, stats/size/age,
alignment/racewar/hometown, skills/spells/slots, epics/money/items, equipment,
pets/mount links, guild/trophies, timers and affects, as applicable.

| Route family | Required ownership and lifecycle distinctions |
| --- | --- |
| Ascension/descension in `actoth.c` | Keep the disabled Paladin -> Agathinon/Avenger, Theurgist -> Eladrin/Theurgist, Avenger-spec and Necromancer -> Lich paths, their costs/callbacks/state changes and actual denial gates. `do_ascend` rejects PCs; its Theurgist helper rejects NPCs. `do_descend` returns disabled before mutation; `do_old_descend` has no discovered active registration. Helpers and historical room comments do not establish access. |
| Legacy conversions in `specs.room.c`, `specs.mobile.c`, `specs.object.c` | Battlerager room and Monk conversion assignments are commented out. Dragonkin's `dragonlord_plate_old` is unbound; object 25723 uses the different spell-effect handler. Account for these without enabling them or confusing other acquisition routes. |
| Revenant crown | Object 22070 -> worn periodic dispatch -> NOSAVE `TAG_RACE_CHANGE`, race/age/equipment change -> event removal, generic cleanup, death, capture/load. Reuse existing native/world regressions. Current capture projects original race and removal birth policy without changing the live form; death cleanup restores that birth policy before capture. Original pre-form birth is not stored. Ordinary crown acquisition remains open. |
| Draconic Apotheosis in `skills.c`, `magic.c`, `affects.c`, `fight.c` | Dragoon circle-12 grant, mount requirement/removal, old-race affect, Dragon mutation, damage and reversal. Creation-disabled Dragoon does not disable existing-character use. |
| Shape/disguise/control transfer in `actnew.c`, `disguise.c`, `innates.c` | Learned shapes and disguise affect effective identity; `morph`/`un_morph` transfer control to/from an NPC body. Connect distinct representations, callers, restrictions and exits. NPC-shaped bodies cannot receive a blanket exclusion. |
| Affect forms in `magic.c`, `necromancy.c` | Vampire/angelic forms, bonuses, pets, spell slots and innate-gated `do_remort` reversal; wraith/phantasmal and other consumed flags. Corpseform's disabled dispatch/body/reversion remain connected with denial evidence; its comment is not proof of a defect. |
| World/exceptional routes | `specs.shabo.c` tower rooms 32907–32909 and reversal; Harpy mobiles 31109/31124, feather cost and race/faction/alignment changes; name-gated `spell_curse_of_yzar` in `spells.c`. Use actual target providers for dynamic forms. Classify staff setters, NPC initialization, legacy load and display substitutions through exact bindings/exclusions. |

Qualify the following acceptance cases using existing tests first. Extend the two
existing journey files instead of adding a separate test program per mechanic.
Share setup across cases; maintain independent expected outcomes.

| Family | Required behavioral acceptance |
| --- | --- |
| Creation | Telnet and WebSocket menus/submissions, legal/forbidden race/class/alignment, disabled Dragoon/restricted races, admission denial, starter kit/abilities, save/relog; transport differences remain explicit. |
| Specialization | Mortal teacher command at/below 30; wrong teacher/race/slot, existing spec/multiclass/timer denials; skills and relog. Unspecialization covers funds, invalid submission, completion and ledger failure semantics, successful cost/reset and spell removal. The actual epic service debits and calls completion before queuing its ledger; do not invent asynchronous rollback on enqueue failure. Reuse `test_epic_in_memory.py` and `test_unspecialize_guard.py`. |
| Effects/restrictions | Guardian/Bulwark at 40/41, shield/no shield, correct/wrong spec and bypass, shipped 0.850 and changed-property behavior, through actual damage application. Active innate dispatch/cooldown/effect, racial stats and body/item restrictions; primary/secondary and true/displayed/effective race distinctions. A raw-damage stub cannot prove HP changes. |
| Multiclass | Assigned room path for Human and Orc; invalid race/pair/morph, repeat and threshold denials; before/after identity, level/XP, skills/spells/epics/guild/trophies/playtime; secondary learning/caps/stat effects; save/relog. |
| Progression | Side-cap and Hardcore restrictions, level/circle boundaries and resulting grants. Reuse isolated level-cap database tests for qualifying frags, timer/unlock and persistence; retain the separate flat-file evidence boundary. |
| Disabled/legacy | Actual ascend/descend/corpseform denials without mutation, consumption or cost; unassigned conversion helpers do not become accessible. |
| Transformations | Each distinct state representation enters through its real route, produces an observable mechanic and exits through applicable expiry, manual removal, death, extraction, quit/relog, restart and conflicting-form paths. Each route declares which exits apply and why; shared lifecycle evidence names every covered option. Permanent/world/item/affect/disguise/control routes all remain in scope. |
| Acquisition | Follow assigned/loaded prototypes, resets, quest/item grants, trainers and room access through real dispatch before calling a route ordinarily reachable. Staff-spawned crown, supplied levels and teleportation remain narrower fixtures. Unfinished acquisition stays unresolved. |

Use actual initialized tables/predicates for exhaustive finite identity and ordered
pair traversal, including denials and boundary levels/circles; test overrides
separately. Traversal proves safety/structural consistency, not policy correctness
without independent expected outcomes. Preserve pre/post successes, denials,
messages, costs, mutation order and persisted state for changed code under identical
configuration and random inputs. Untouched individual mechanics may remain explicitly
unverified; that does not excuse missing connections or any required case above.

**Exit:** every transition has entry/lifecycle/persistence ownership; the required
family cases pass or identify a specific existing defect with a failing assertion.
A newly introduced failure blocks completion. Existing gameplay defects stay
separately scoped and visible as incomplete; do not change access policy to make
an acceptance case pass.

### 4. Prove detection, run the final gate, and document the result

The validator must resolve unique IDs, owners, masks/slots/dimensions, dependencies,
target providers, native binding types, registrations, passives, transition fields,
applicable cleanup and persistence. Test bindings use real mechanic/route IDs and
exact assertions, not filenames alone. Keep these mutation categories in the
existing suite; one case per distinct failure mechanism is enough when shared
coverage is explicit. Add another only for a materially different path.

| Deliberate mutation | Required failure |
| --- | --- |
| New race/class/spec, grant or transformation target without connections | Name the missing option/relationship. |
| Removed command/spell/object/mobile/room registration with handler retained | Fail binding/access validation. |
| Passive grant retained but effect consumer removed | Fail implementation coverage. |
| New branch, alias/helper caller, identity write or assignment, including a new source file/header | Report the unregistered site; existing metadata/exclusions cannot cover it. |
| Incompatible overwrite of a grant cell | Detect conflict before final-table overwrite hides it; preserve declared intentional precedence. |
| Changed prerequisite/property/target/callback/cleanup dependency | Invalidate affected proof; fail the relevant behavioral assertion when the outcome changes. |
| Removed/renamed/skipped test or stubbed claimed implementation | Report missing/unverified evidence, never promote stale success. |
| Broadened/removed exclusion without resolving the condition | Fail the exact exclusion's diagnostic/case. |

Run mutations in temporary fixtures under `bin/`. Reuse stable native objects
within a run, as the existing test already does; do not compile every unchanged
translation unit for each variant. Keep ASan/UBSan failure fatal. No cross-run
cache project is needed.

During implementation, run the smallest affected tests and `make -C src` after
C/C++ changes. Group related edits before validation and keep inputs stable while
tests run. Reuse passing evidence whose code/configuration/assertions/world inputs
are unchanged. A source check does not replace an executable test. Reflection's
existing test stubs its spell effect; item-race tests do not cover all body/equipment
rules; help checks are documentation evidence only.

At the completed candidate, run the required integration gate once:

```bash
./scripts/format.sh --check
git diff --check
make test-all -j8 TEST_JOBS=8
make -C src -j4 pfile
make -C migrations/tools -j4 all affects pfile_converter
python3 tests/async/test_documentation_contract.py
```

`make test-all` includes maintained development/production/editor/world builds and
the discovered native/journey tests. Do not separately repeat those same passing
runs at that candidate. Run applicable isolated database cases through the existing
[TESTING.md](../guides/TESTING.md) wrappers, including
`tests/async/with_disposable_mariadb.sh python3 tests/async/run_level_cap_mysql.py`
for the live progression claim. No production operations or shared services.
If a gate fails, repair/retest the focused failure, then rerun only invalidated
checks and any required final gate. Record the actual aggregate result; a focused
repair does not turn an earlier failed aggregate run green. Do not wait for CI.

Document how to follow the connections and interpret test output in the existing
[documentation index](../README_docs.md), with a concise reference if needed.
Documentation consumes the code; do not maintain a duplicate rules catalogue.
Keep current checkpoint/results here and per-defect evidence in REGRESSIONS.md.

## Evidence and completion rules

Access (**available, conditional, disabled, unresolved**), implementation
(**connected, incomplete, legacy**) and proof (**named assertions passed, failing,
unverified**) are independent. Disabled routes can have proven denials; conditional
routes can be incomplete; existing characters can use creation-disabled options.
No editable `verified` flag or diagnostic status may alter gameplay.

Each proof names its assertion, route/mechanic ID, configuration, backend, fixtures,
actual production dependencies and tested inputs/revision or binary identity.
Changed relevant inputs invalidate only the affected proof. A precise gap names
the rule/site, missing or failing assertion, and reproduction/open question. Neither
a vague exclusion nor a historical green run can conceal unfinished work.

Completion of issue #52 requires all four batches: every scoped definition and
site accounted for; all required relationships connected to real owners or precise
existing gaps; forward/reverse and mutation checks complete; required behavior and
lifecycle evidence current; behavior-preserving changes verified; documentation
and required local gates complete. No unclassified sites, blanket exemptions,
unverified refactors, or newly introduced failures may remain. Report unresolved
ordinary acquisition and existing defects at their actual scope instead of claiming
that every option is playable. Do not start another hardening phase after these
conditions hold.

The cuts in this revision are duplicated chronology, repeated full-suite/build
runs per connection, handwritten copies of table-derived grants, duplicated shared
rule bindings, and speculative test/framework expansion. Exact ownership,
registration-write conflict detection, reverse coverage, all route families and
the required behavioral evidence are retained.
