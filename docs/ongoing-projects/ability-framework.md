# Shared ability framework

Status: proposed implementation plan. Framework implementation and ability conversion are pending.
Date: 2026-11-04
Primary source baseline: fetched `origin/master`, `264c4879114a03fdf33169a57466c4f14de24101`.
Reference Rust baseline: `4492942d68718fb0443539084d538f922e044b1e` in the sibling `duris-rs` checkout.
Reference feat-system baseline: `85fed29152fca9ae5951686827c1e70bd1a22a1a` in the sibling `Luminari-Source` checkout, reviewed 2026-11-04.

## 1. Outcome

Build one framework for the numerical mechanics and descriptions of spells, skills,
bard songs, epic skills, and racial/class innates. An ability's gameplay and its
player-facing explanation must obtain each converted number from the same definition.
The framework must support editable formulas, trustworthy previews, gradual adoption,
and continued use of the existing ability handlers.

Build the core separately in new files. The first deliverable is a standalone library,
catalog, command-line tooling, and executable tests. Server integration follows as a
distinct milestone with small, named adapters. An initial core implementation must be
buildable and verifiable without changing the production server's object list,
startup, command routing, persistence schema, or combat handlers.

Players continue through `spells info <name>` and `skills info <name>` and gain verified
mechanics as abilities are converted. The singular forms used in conversation follow
the interpreter's existing abbreviation behavior. Innates use the same framework and
gain an information entry point after checking the existing innate command grammar.

The requested end state includes the capabilities demonstrated by the Rust framework.
A registry of handwritten preview functions can serve an early conversion, but the
complete project also delivers the expression engine, catalog validation, coverage
tracking, change previews, controlled publication, and structured client output.

### Requirements established by the discussion

- One shared framework across ability kinds.
- Separate files and an initially independent build.
- Incremental adoption, with the current information page available for uncovered abilities.
- Shared calculations between execution and explanation.
- Source-grounded conversion of current Duris behavior.
- Use the Rust implementation and its design history to improve our design.
- Apply useful patterns from Luminari's feat system where they clarify existing Duris mechanics.

The architecture, file names, storage choice, phase boundaries, and estimates below
are proposed implementation decisions. This document records a plan, with future
delivery gates explicitly marked as pending.

## 2. Current Duris foundation

The existing [spells browser](spells-command-browser.md) and
[skills browser](skills-command-browser.md) already provide name resolution, public
versus staff access, class/spec catalogs, character-specific access/progress, paging,
and help integration. Their implementation intentionally limits generated mechanics
to what the existing metadata establishes.

The main owning sources are:

- [src/cmd/spells.c](../../src/cmd/spells.c), especially `spell_info`.
- [src/cmd/skills.c](../../src/cmd/skills.c), especially `skill_info`.
- [src/classes/skills.c](../../src/classes/skills.c), which initializes spell/skill definitions and grants.
- [src/net/sparser.c](../../src/net/sparser.c), including `SpellCastTime` and the casting branches around it.
- [src/classes/memorize.c](../../src/classes/memorize.c), including effective circles, preparation, and resource consumption.
- [src/magic/magic.c](../../src/magic/magic.c), class spell files, and [src/cmd/actoff.c](../../src/cmd/actoff.c), which contain ability calculations mixed with their actions.
- [src/combat/fight.c](../../src/combat/fight.c), which applies shared spell, melee, and final damage rules.
- [src/classes/innates.c](../../src/classes/innates.c), including active uses, passive hooks, and `check_innate_time`.
- [src/classes/epic_skills.c](../../src/classes/epic_skills.c), including prerequisite proficiency, exclusions, acquisition paths, and training costs.
- [src/core/random.c](../../src/core/random.c) and [src/core/utility.c](../../src/core/utility.c), which own `number` and `dice` semantics.
- [src/world/properties.c](../../src/world/properties.c), which owns current property values and their overload-specific numeric conversions.

`SpellCastTime` already combines base beats with racial timing, personal spell pulse,
haste, and flurry. Other casting branches apply additional behavior. Resource use can
consume mana, a spell slot, or a memorized copy and can include chance-based exceptions.
The framework's information adapters must follow these actual paths.

The sources are compiled as C++20 under the strict warning profile in
[src/Makefile](../../src/Makefile). MariaDB and flat-file builds are both maintained.
The new core should use the standard library and the existing cJSON dependency for
catalog I/O. The strict parsing and whole-document publication pattern in
[studio_ability_model](../../src/item/studio_ability_model.h) and
[studio_abilities.c](../../src/item/studio_abilities.c) is a useful local precedent.
Its item-trigger types have a different responsibility from this numerical framework.

### Initial sizing evidence

A comment-aware scan of the literal `SPELL_CREATE*` and `SKILL_CREATE*` registrations in
`initialize_skills()` and its `create_epic_skills()` helper found 640 distinct spell names
and 245 distinct skill names. The skills include 52 epic skills, 19 songs, and 6
instruments. Matching by kind and exact name against the pinned Rust
`data/gamedata/skill.csv` found 881 counterparts, 752 with tooltip rows, and 605 with
formula rows. The epic-skill counterparts have neither row type. This is an exploratory
source inventory. It includes entries whose current public eligibility needs to be
established from the initialized registry, and it does not enumerate player innates or
prove numerical equivalence.

Milestone P0 replaces these counts with an authoritative inventory of supported
registrations, current class/spec grants, playable innates, and actual call sites.
Every existing caller of a converted ability remains in scope, including NPCs,
scrolls, wands, potions, item procs, and nested casts.

## 3. Lessons from the Rust project

The reference implementation has a common ability/formula table, a typed expression
compiler, an execution evaluator, a range evaluator, display templates, native custom
values, and editor previews. The historical plan at `3ababc34` explains the original
design. The current design's sections 14-29 record the changes required during its
implementation. The specific source references are collected in section 15.

Carry forward these useful choices:

- Named formulas express roles such as damage, absorption, duration, and cooldown.
- Gameplay and presentation consume the same numerical definitions.
- The expression language is bounded, compiled at load, and supports typed arithmetic.
- Migration tools propose edits and record unresolved sites for review.
- Old code is retained in test fixtures to check values and random behavior.
- Designer changes can be previewed across levels, classes, and specializations.
- Formula edits and their display templates are published together.

Make the following stronger contracts explicit in our design:

1. **Missing required mechanics reject activation.** The reference loader can fall back
   to shipped rows and ultimately yield zero for broken formulas. Our registry must
   distinguish an uncovered legacy ability from an invalid converted definition.
   Gameplay never interprets a missing required result as zero.
2. **Target assumptions are data.** The reference environment can substitute the caster
   for an absent victim. Our preview records an absent target explicitly and presents
   only supported facts or clearly named scenarios.
3. **Damage has a declared stage.** Their initial raw damage tooltips needed correction
   for the shared damage pipeline. Each effect here declares its units, damage route,
   and calculation stage before any number is presented.
4. **Coverage measures mechanics as well as prose.** A text line is useful, but separate
   counters track described effects, shared execution sites, verified bounds, native
   exceptions, and complete abilities.
5. **Bounds carry evidence.** Conservative ranges and exact extrema are distinct.
   Native custom values require an explicit range provider or an honest unavailable
   result. Evaluating every roll low and then high does not establish general extrema.
6. **Publication preserves live edits.** Their history added atomic multi-table imports
   and three-way comparison after editor changes became possible. Our catalog uses a
   complete generation, expected-base checks, and conflict detection from the start.
7. **C++ behavior owns the conversion.** Rust formulas, descriptions, and tests provide
   candidates. Current C++ arithmetic, sequencing, properties, and gameplay determine
   the accepted result.

These are design requirements derived from inspected behavior and implementation
history. They are not a claim of a complete audit of the Rust engine.

### Findings from Luminari's feat system

The source review found five transferable improvements. These extend the contracts
below and their milestone gates while retaining current Duris rules as the authority.

1. **Requirements can explain their own results.** Luminari attaches typed prerequisite
   records to a feat. `meets_prerequisite` evaluates them for learning, and
   `display_feat_info` calls that evaluator to highlight unmet requirements. Our plan
   adopts structured checks with reasons, so the info page can explain which current
   Duris requirement is missing. Luminari also has global gates and a separate native
   special-case branch in `feat_is_available`. Our coverage must account for those
   kinds of checks as well as declarative records. [Feat rules and display](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/src/character/feats.c)
2. **Acquisition, possession, and use are distinct.** `feat_info` separates implemented,
   learnable, and repeatable flags. Class/race grant tables distinguish automatic grants
   from selectable choices, while `get_feat_value` includes applicable stored, equipment,
   and form-specific contributions. Our context must preserve the source and effective
   meaning of a grant. This prevents a learning prerequisite from accidentally blocking
   an independently granted innate. [Feat metadata](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/src/character/feats.h),
   [grant records](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/src/character/class.h),
   [effective values](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/src/core/utils.c)
3. **Relationships can drive navigation and change review.** Luminari's feat page derives
   its prerequisite dependents and class/race acquisition lists from the registries.
   Our catalog can derive `requires`, `unlocks`, and `granted by` views and the affected
   consumers of an edit. Duris already has prerequisite and exclusion relationships in
   `epic_teachers`, giving this a concrete local use. [Feat information](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/src/character/feats.c),
   [Duris epic prerequisites](../../src/classes/epic_skills.c)
4. **Use limits need one inspected binding.** Luminari links daily-use feats to recovery
   events and provides separate queries and spending functions. Its racial ability table
   also connects a feat, delegated spell, target mode, flags, and command. Our plan adds
   explicit invocation and use bindings, allowing a spell-backed innate to share effect
   math while retaining its own access, lag, and recovery contract. [Use queries and spending](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/src/core/utils.c),
   [racial ability bindings](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/src/act/act.other.c)
5. **Registry wiring deserves behavioral checks.** Luminari's tests cover automatic
   versus learnable grants, stacking, cooldown/event wiring, refusal without ownership,
   and the exact point where an action spends a use. Our acceptance matrix adds these
   boundaries to numerical equivalence. [Racial feat tests](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/unittests/CuTest/test_racial_innate_feats.c),
   [converted skill tests](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/unittests/CuTest/test_rol_feats.c)

The inspected feat descriptions remain authored text, and much of their effect logic
lives in gameplay files. The advantages above concern metadata, relationships, and
state contracts. New Pathfinder feat purchases, ranks, action-economy rules, and daily
recovery schedules require their own gameplay proposals. The feat review was a source
inspection, including test bodies; its test suites were not executed for this plan.

## 4. Architecture and proposed files

Data and results flow through these boundaries:

```text
Versioned definitions + compiled usage contracts
                    |
           parser / validator / compiler
                    |
            immutable catalog generation
                    |
       execution values     preview facts
              |                  |
      narrow game adapters   text / GMCP / admin renderers
              |                  |
      existing ability code  existing info commands
```

The standalone core receives value snapshots and explicit services. Keep game
pointers, global registries, sockets, SQL, Redis, world mutation, and the event loop
inside the integration adapters. The core can therefore be exercised in an ordinary
native test executable using synthetic characters and recorded roll tapes.

Proposed source layout, introduced as the relevant milestone needs it:

```text
src/abilities/
  model.h                         IDs, contexts, units, facts, diagnostics
  catalog.h / catalog.c           immutable definitions and generation validation
  requirements.h / requirements.c
                                  pure checks, explanations and relationship indexes
  formula/                        typed IR, parser, compiler, execution and ranges
  preview.h / preview.c           facts, assumptions and effect descriptions
  native.h / native.c             reviewed native providers and their contracts
  game_adapter.h / game_adapter.c
                                  current Duris metadata, properties and roll adapter
  integration/                    info, GMCP and staff publication entry points
  cli/                            standalone validator, preview and comparison CLI

lib/abilities/
  manifest.json                   schema version, shards and bundle identity
  spells/*.json                   definitions grouped by owning family
  skills/*.json
  songs/*.json
  innates/*.json

scripts/abilities/                inventory and reviewed conversion tooling
tests/abilities/                  engine, parity, bounds and loader tests
tests/async/                      existing command tests plus integrated journeys
bin/ability-framework/            binaries, reports, traces and temporary catalogs
```

File names are a proposed responsibility map. Keep small related implementations
together until their size or dependencies justify a split. Shared effects have one
owner even when several classes grant the abilities that use them.

P1 builds the standalone targets through a dedicated script. Add server build wiring
only in P3. Subsequent changes to existing files are limited to adapters, calculated
value handoffs, lifecycle hooks, and the specific conversion under review. Source
reorganization of unrelated game files is outside this migration.

## 5. Shared contracts

### Ability and effect identity

Use `AbilityKey { namespace, legacy_id }`. The namespaces distinguish the existing
skill/spell table from the innate table. Presentation records distinguish spells,
ordinary skills, epic skills, songs, instruments, and innates. Preserve existing IDs
and use compiled constants when generating the catalog's symbol map.

An ability can contain several effects, each with a stable local ID such as `hit`,
`burn_tick`, or `shield`. Formula and fact identities include that effect ID. This
supports spells with multiple hits, damage types, targets, timers, and reductions.
Aliases reference an owning definition with an explicit parameter mapping.

### Definition contents

Each versioned definition contains:

- Ability key, canonical symbol, revision, and source provenance.
- Effect IDs and the supported use contexts for each effect.
- Named typed formulas, typed parameters, result units, and dependencies.
- Structured fact declarations and templates referencing those formulas.
- Conditions governing which facts apply, with references to shared predicates.
- Acquisition/access/use checks, grant-source projections, and explicit choice bindings.
- Invocation bindings and use-limit queries tied to their existing runtime owners.
- Required game inputs and whether each can be used in public previews.
- Damage/healing stage and route, timing units, and per-use versus per-hit meaning.
- Coverage state and the compiled usage contracts the definition satisfies.

Use schema-versioned JSON for the initial source format. Formulas are strings, so the
JSON parser does not round their numeric literals through a double. IDs, revisions,
and limits receive explicit integer validation. Reject duplicate keys, unknown fields,
unknown IDs, cycles, invalid templates, unsupported versions, and excessive input size.
Reuse the repository's strict cJSON patterns without importing game headers into the core.

Class grants, current proficiency, spellbook access, and existing authored help continue
to come from their owning services. Templates describe verified mechanics. They refer
to authoritative quantities and conditions wherever these can be shared.

### Requirements and explanations

Represent deterministic checks as typed requirement nodes using `all`, `any`, and
explicit exclusions, with leaves backed by the current game's pure predicates. A
result carries the rule ID, `met`, `unmet`, or `needs_context`, relevant observed and
required values, a player-safe explanation, and the rule's owning source. Boolean
grouping uses the same pure evaluator/native-provider registry as the framework.
Validation rejects requirement predicates that draw randomness or mutate game state.

Each check declares its purpose: catalog visibility, learning, effective access, or
current use. Class/circle access, an epic training prerequisite, a prepared spell,
equipment restrictions, and an exhausted innate timer belong to different purposes.
Unknown checks must not be reported as satisfied. Random saves and combat chances
remain outcomes or probability facts rather than deterministic readiness requirements.

Initially, adapters project existing rules and retain native checks for exceptions.
When a predicate is shared, both the gameplay gate and the info page call it. Declarative
checks and native checks compose explicitly; adding one record must not suppress an
existing special-case check. Keep rule coverage in the usage manifest. A readiness
result identifies the checks actually performed and any remaining context needed.
Execution rechecks mutable conditions at the original action boundary.

Generate reverse relationship indexes once per validated generation. Keep learning
prerequisites, grant sources, formula dependencies, and delegated invocation edges
typed separately. Use them for player navigation and edit-impact previews. Reject
missing references and formula cycles, and diagnose prerequisite cycles against actual
grant paths rather than treating every graph edge as the same dependency.

### Grants, ranks, and bound choices

Expose effective access through a `GrantView` projected from the existing owner. Include
the contributing race, class/spec, learned state, form, item, or other supported source,
the effective unlock/cap/value, and the aggregation policy used by current mechanics.
Distinguish possible sources from the sources applicable to this character now. Where
historical acquisition provenance was never saved, report that limit rather than
reconstructing an invented training history.

Duris's `innate_unlock_level` takes the earliest applicable race/class unlock, and
`has_innate` turns that into boolean access. Two qualifying sources therefore continue
to grant that same access. Luminari's additive feat ranks and repeatable weapon choices
illustrate why an aggregation policy must be explicit. Support ranks or bound choices
only where the inventoried Duris mechanic already has them. Skill proficiency, repeated
training, effect stacking, and possession are separate values.

A choice required by an actual ability uses a typed binding, such as the selected
weapon or form. The binding is included in evaluation and preview cache identity.
An omitted required choice returns `needs_context`. The same requirement cannot be
satisfied by one weapon while the displayed numbers silently use another.

Actual-character contexts and hypothetical planning contexts carry separate mode tags.
Proposed levels, equipment, or training in a staff preview stay in a read-only overlay
and are labeled as a scenario. They cannot become an actual ownership or readiness result.

### Invocation and recovery bindings

An `InvocationBinding` connects the source ability to the effect implementation it
uses, with effective-level mapping, cast kind, target mode, selected inputs, and the
owner of costs and recovery. A racial innate invoking a spell keeps its own access and
spending rules while referring to the shared spell effect. These bindings initially
describe and validate existing handlers; they do not introduce a second dispatcher.

A `UseContract` identifies existing resource state, maximum and remaining uses,
recovery clock and timing, cooldown identity, and the exact spending point. Read-only
queries serve previews. Gameplay spending stays at the source-verified call site.
Validate binding consistency across the ability, handler, state query, and timer/event.
Shared recovery pools must be declared explicitly rather than inferred from names.

Our existing `can_use_innate` supplies a read-only availability check, while
`check_innate_time` creates or changes `TAG_INNATE_TIMER`. Extend a read-only projection
of that state for detailed remaining uses/time. Preserve the actual recovery model.
Luminari's daily-use event replenishes uses individually, while the current Duris
innate timer has its own batch-reset behavior.

Record refusal, attempted use, successful effect, resistance, and cancellation outcomes
where they change resource spending. Luminari's racial spell-like handler tests whether
certain effects committed before spending, while other commands have different policies.
Each Duris conversion must retain its existing policy. Tests must establish when a
failed action spends a use, as well as when it keeps one.

### Context and time

An evaluation context identifies the caster, effective cast level, invocation kind,
selected weapon, optional target, relevant room conditions, and current property view.
It also carries effective grant results and any required bound choice from the shared
queries above. Hypothetical overrides have their own mode and cache scope.
Effective cast level is distinct from character level. Scrolls, wands, NPCs, and nested
casts must retain the values their callers supply.

Represent missing fields explicitly. Inputs required for gameplay must be present before
that evaluation stage starts. A preview can return `needs_target`, `needs_equipment`,
or another named dependency instead of inventing a default actor or target.

Contexts are immutable and short-lived. Rebuild them when the original code would
read changed state, including after a save, guard interception, equipment change,
target extraction, or an event tick. Separate effect durations, action lag, cooldowns,
rest periods, and scheduled tick intervals. Render seconds from the actual engine
constants and use a pure clock input for remaining-time calculations.

## 6. Formula execution, randomness, and previews

### Expression engine

Provide a small typed expression language with integer and floating-point arithmetic,
comparisons, lazy conditionals, named formula references, parameters, bounded dice and
number rolls, and an allowlist of pure context functions. General scripting and world
mutation remain responsibilities of the game handlers.

Start with `bool`, `i32`, `f32`, and `f64` scalar types plus result-unit annotations.
Add an unsigned or wider integer type when the inventoried source requires its exact
semantics. Keep such a site behind a verified native provider until that type exists.

Compile to one canonical typed representation. Produce compact execution instructions
and a range-evaluation representation from that same checked input. Both evaluators
share the arithmetic rules. Resolve identifiers and provider capabilities at load.
Validate work, nesting, dependency, and roll-count limits. Playback on the combat path
must have bounded storage and require no parsing, disk access, or database query.

Our default integer arithmetic is checked within its declared domain. Each migrated
expression must prove the relevant domain or document a deliberately defined operation.
C++ signed overflow, invalid shifts, and out-of-range conversions require investigation
and a separate behavior decision before activation. Unsigned modular behavior can use
an explicitly typed operation. Preserve intermediate float/double widths, casts,
integer truncation, and property-overload behavior on supported inputs.

C++ operand and argument evaluation can be unspecified. Record the old execution's
observable roll sequence under supported build profiles. Multiple side-effecting
operands need an explicit sequence before automatic conversion. If supported builds
disagree, the discrepancy becomes a documented mechanics decision and blocks that
conversion until resolved.

### Execution scopes and rolls

Give each calculation stage an evaluation frame. A memoized named roll is evaluated
once when the corresponding original local value was created. Repeated hits, targets,
and periodic effects receive fresh frames or an explicit fresh-sample operation.
Parameterized functions declare their sampling behavior. Cache identity includes the
catalog generation, context, and assumption scope.

Inject the game's existing `number`/`dice` behavior through an execution-only roll
service. Preserve clamping, reversed bounds, equal-bound behavior, roll arguments,
call order, and draw count. A save or chance test stays at its existing point in the
handler and supplies its outcome or parameters to subsequent calculations.

Preview evaluation has no access to that roll service, skill training, resource
consumption, event scheduling, or gameplay mutation. Live shadow comparisons must use
recorded inputs and rolls, with the original execution occurring once. They must never
run a second ability handler against the same live world.

### Range and probability quality

Every numeric preview reports one of `exact`, `conservative_bound`, or
`context_dependent`, with its assumptions and units. Formula absence is a separate
coverage result, and evaluation failure is a diagnostic.

Use interval rules that account for sign changes, division around zero, integer
boundaries, floating-point rounding, lazy branches, and correlated rolls. Unsupported
operations produce a dependency or diagnostic result. Random branch sampling alone
does not prove a bound or an exact probability.

Small finite domains can be enumerated to prove extrema and probabilities. Larger
domains use validated conservative bounds, supported by property tests and adversarial
cases. Native providers must supply execution semantics and a reviewed preview
contract. Endpoint evaluation is accepted only with a monotonicity argument.

Skill proficiency, a nominal chance threshold, and final success probability are
different facts. Preserve that distinction for contested actions, skill-notching
exceptions, multiple saves, and immunity rules.

### Damage and healing

Label values by stage, including base roll, caster-adjusted output, and a result
against a supplied target. An unselected target's resistances, saves, shields, health,
and hidden properties cannot be presented as known.

Factor read-only numerical steps out of the existing damage/healing helpers as each
conversion needs them. Record the correct route and flags per effect, including
no-reduction attacks and damage to walls or objects. Reuse these steps for previews
and execution, preserving their original placement among saves and other effects.
Public output can show conditional results such as a failed-save amount when the
assumption is explicit. Actual outcomes continue to depend on execution-time state.

## 7. Coexistence and fallback

Track coverage per effect and fact. Suggested states are `legacy`, `shared_native`,
and `formula`, plus separate verification and presentation status. An ability becomes
complete only when its required effects and supported invocation sites are accounted for.

The info commands first render existing identity/access/progress information. They
then request verified facts from the framework and append available facts before the
authored help. A wholly uncovered ability produces the current information page.
Partial coverage can expose a verified cooldown while a target-dependent chance is
still being converted. Internal state names belong in staff diagnostics.

The gameplay transition occurs at named numerical call sites. A shared-native provider
can establish a calculation contract before a formula-backed implementation replaces
it. Each numeric result used in gameplay has one selected implementation, and the
preview identifies that same implementation and generation.

An entry missing because it has never been converted selects the existing gameplay
path. A broken converted definition rejects catalog activation. A rollback selects a
complete compatible generation or a certified native provider before an invocation
starts. After rolls, costs, or effects have occurred, execution must never restart
through the old handler as a fallback.

Each converted stage needs a tested error outcome. Validate before the next associated
mutation, return a typed failure, record the ability/effect/generation, and follow the
handler's reviewed cancellation path. Preserve already committed costs and outcomes
according to that contract. The C++ engine has no whole-spell transaction to undo them.
Failures must remain observable and must not be converted to ordinary zero results.

Information lookup may be disabled independently of formula execution. Activation
controls belong to the catalog and staff configuration, and only select implementations
that have passed equivalence checks for that server build.

## 8. Catalog publication, persistence, and ongoing effects

Use immutable, versioned bundles shared by MariaDB and flat-file builds. Keep gameplay
formula reads in memory. The initial store is a directory of validated generations and
a small active-generation pointer, with a complete shipped baseline as a recovery option.

Publication proceeds through a draft, validation, before/after preview, expected-base
check, durable write, and activation at an event-loop boundary. Validate formulas,
fact templates, shared predicates, and invocation contracts as one bundle. A preview
receipt identifies the executable compatibility version, candidate hash, base generation,
and property snapshot. Stale receipts require a new preview or explicit conflict handling.

Release updates compare the previously shipped value, the new shipped value, and the
operator's active value. Conflicting edits reject the update with specific records.
Write new files completely, sync them as required by the supported platform, and atomically
replace the active pointer only after the generation is durable. Test crashes around
every publication boundary. The audit journal records intent and outcome keyed by the
generation, so startup can reconcile a durable activation interrupted before its result
was logged. Concurrent editors use expected-base checks to avoid lost updates.

Reject invalid candidates while retaining the last compatible validated generation.
At startup, an invalid active generation must produce an explicit operator diagnostic
and use a verified compatible recovery generation. If none exists, keep affected
converted abilities unavailable until repaired. A valid baseline must accompany every
release that depends on converted definitions.

A synchronous evaluation retains its generation through completion. Ongoing casts,
affects, and recurring events follow the original ability's read timing. Values already
stored on an affect stay stored. Events that historically reread numbers each tick may
take the active generation at that tick, while an ability that captured its values at
cast time retains those values. Document this per effect and test reload, rent, reboot,
world-preserving hotboot, fresh-world copyover, and restoration at those boundaries.

Persist generation identity or extra values only where the supported effect actually
requires it. Any such extension must cover both backends and older saved records in
its own migration work. Never serialize process-local pointers or catalog handles.

## 9. Interfaces and editing workflow

Use one structured `AbilityInfo` result for text, client messages, and staff preview.
It includes canonical identity, authoritative access/preparation facts, effect facts,
units, calculation stage, assumptions, quality, and a schema version. Requirement
results, applicable grant sources, and prerequisite/dependent links use the same model.

- **Text** extends the current spells/skills info handlers and their pager, colors,
  help aliases, and access checks. Preserve exact-match and ambiguity behavior.
  Show unmet requirements with an explanation, and derive prerequisite/unlock links
  from verified relationships. Preserve public visibility rules for those links.
- **Innates** use the existing innate grant/timer rules. Introduce an `info` form only
  after inventorying name and command collisions. Inspection must use a read-only
  timer query, since `check_innate_time` can consume a use.
- **GMCP** provides a versioned request/response using the same result. Rate-limit
  requests and honor session ownership, visibility, and staff-only fields.
- **Command-line tooling** validates bundles, displays coverage, previews a character
  fixture, compares two generations, and emits machine-readable diagnostics.
  Edit impact includes affected formulas, callers, requirements, and dependent abilities.
- **Staff editing** offers draft, diff, validation, level/spec preview, publish, history,
  and revert. The CLI ships first. A DurisWeb editor is a later deliverable against the
  same format and publication rules, with repository-specific discovery before design.

Public target-sensitive previews can use explicitly labeled hypothetical targets.
Any future request for a real target must follow the normal visibility and targeting
rules and must not disclose hidden defenses or equipment. Candidate edits are shown
as proposed values until the corresponding gameplay generation is active.

## 10. Conversion tooling and evidence

Build an inventory from actual initialized definitions and compiled call sites. A
test-only exporter links the production initializers under the supported build flags.
Reconcile configuration-dependent grants with read-only evidence from an isolated local
game. Write exports and intermediate analysis under `bin/ability-framework/`. Include
public grants, staff/internal entries, disabled abilities, stubs, aliases, songs, passive
skills, and innates as separate scopes. Explain exclusions. An ability referenced by
items or NPCs still requires caller compatibility when its player-facing form is converted.

Use compiler-aware analysis where macro expansion and C++ types matter. A conservative
source scanner can identify candidates, but it must preserve unresolved cases rather
than claim an expression is pure from its spelling. Use the existing build flags and
constants, including the relevant build profile and backend configuration.

The converter emits a reviewable proposal containing:

1. Ability/effect identity, baseline commit, source function and source hash.
2. Each extracted expression, its inputs, type conversions, reads, and roll sites.
3. Proposed formula rows, fact declarations, and the smallest call-site edits.
4. The original executable expression or function fixture used as the test oracle.
5. Values, roll traces, and effect outcomes to compare, including branch boundaries.
6. Unsupported sites and the reason each remains unresolved.

Applying a proposal verifies the source hash so a concurrent gameplay fix cannot be
overwritten by a stale conversion. Match Rust candidates by ID, kind, canonical name,
and current semantics. Copying a reference row never supplies equivalence evidence.

Coverage reports must show the denominator and report several independent measures:
abilities with metadata, abilities with prose, effects with verified numeric facts,
gameplay sites routed through shared calculations, exact versus conservative previews,
remaining native exceptions, and completely migrated abilities. A coverage ratchet
must detect removal of a required effect or caller even when a text line remains.
Include rule, grant, invocation, and recovery bindings in this accounting. An enabled
catalog entry needs a valid owner and implementation disposition appropriate to its
active/passive behavior. Every selected-variant or recovery binding needs a tested path.

## 11. Verification and performance

### Required executable checks

- Arithmetic tests against the current C++ calculation, including casts, float widths,
  integer boundaries, reversed `number` bounds, and dice clamping.
- Old/new equivalence under identical inputs and roll tapes. Compare roll arguments,
  sequence, draw count, returned values, costs, lag, affects, scheduled work, and
  relevant terminal outcomes. Matching final RNG state alone is insufficient.
- Boundary contexts covering supported levels, class/spec combinations, effective cast
  levels, equipment, player/NPC callers and targets, missing targets, property changes,
  target death/extraction, and spell-versus-item invocation.
- Independent preview bounds checks, including repeated correlated rolls, conditional
  branches, mixed signs, target assumptions, and scope-separated caches. Exhaust small
  finite cases and preserve evidence for exactness claims.
- Preview-purity checks proving no changed RNG state, HP, mana, memorized spells,
  cooldowns, proficiency, objects, or event queues.
- Loader/publisher checks for invalid and incomplete bundles, incompatible binaries,
  failed writes, stale base generations, concurrent drafts, reload, and restart recovery.
- Command and protocol checks for covered, partial, and uncovered abilities, missing help,
  ambiguous names, staff permissions, and public-information boundaries.
- Requirement checks where each condition fails independently, all/any branches differ,
  a required choice is missing, and a native exception applies. Compare explanation
  results with the real learning/access/use gates and test a stale readiness snapshot.
- Grant transitions covering duplicate sources, removal of one source, form changes,
  specialization changes, applicable caps, and hypothetical preview isolation. Preserve
  each ability's boolean, ranked, or selected-variant meaning.
- Registry checks for invalid requirements, grant sources, delegated effects, and
  recovery bindings. For a timed innate, verify both refusal and committed-use paths,
  exhaustion, recovery, and the current rule for spent uses on failure.
- Normal-entry gameplay journeys after integration, including casting, skill use,
  item invocation, NPC use, and delayed effects relevant to the converted batch.

Extend the existing spell/skill browser tests and their journeys when those handlers
are integrated. Their current focused tests establish useful browser behavior but are
not whole-combat or full-world equivalence tests. Rust golden fixtures are reference
material for our own supported C++ outcomes.

Build changed C++ with `make -C src` and the project's maintained profile checks.
Qualify MariaDB and flat-file builds with separate artifact paths when integration
touches shared headers, lifecycle, or persistence. Run focused native sanitizer tests
and relevant isolated journeys. Record exactly which checks ran and their limits.

### Performance acceptance

Measure on the C++ host against an inline baseline using the same inputs. Cover a
simple spell, a branch-heavy skill, a passive invoked on every hit, and a multi-target
or repeated effect. Include catalog lookup, context construction, property access, and
fact rendering in the measurements where those costs are incurred.

The execution target is bounded, allocation-free work after validation, with identifiers
resolved before the hot path. Proposed initial acceptance budgets are at most 5%
additional time in a representative combat workload and less than 10 ms p95 for a
typical framework preview and its rendering. Establish the workloads, hardware, sample sizes,
and noise before using those figures as a gate. Measure server command latency and
resident memory as well as isolated formulas. Validate the budgets after P2 and revise
them only with recorded measurements and an explicit tradeoff.

## 12. Delivery milestones

Every milestone below is pending. Acceptance requires its evidence, and completion of
one milestone does not imply completion of later integration or coverage work.

### P0 — Inventory and executable baseline

- Export the initialized ability inventory and caller map from the current Duris baseline.
- Identify shared effects, timing/resource helpers, public scopes, and current backend constraints.
- Inventory learning/access/use predicates, grant aggregation, delegated effects, and
  recovery ownership. Record native exceptions alongside declarative metadata.
- Define numeric semantics and representative old-code oracles.
- Record existing command output and the planned behavior of uncovered abilities.
- Finalize schema v1 and the initial native-provider capability contracts.

Gate: every pilot ability has known source ownership, callers, numerical stages,
side effects, and a proposed verification matrix. Inventory disagreements are resolved
or explicitly excluded from a pilot with a reason.

### P1 — Standalone core

- Add the new core files, catalog schema, independent build, and test executable.
- Implement parsing, typing, bounded execution, range results, templates, and validation.
- Add native providers for the minimum pilot inputs and structured preview output.
- Add pure requirement results and relationship indexes to the standalone model.
- Implement generation loading and rejection using temporary test catalogs.

Gate: the standalone executable passes engine, range, and invalid-catalog checks while
the normal server build and handlers have no dependency on the new core.

### P2 — Representative offline conversions

- Exercise Fireball, Heal, Stone Skin, Bash, a multi-target/periodic spell, and a timed
  innate before expanding the first batch to roughly 10-20 representative abilities.
- Include a passive skill or innate to measure high-frequency calls.
- Include one existing epic-skill prerequisite and one innate with multiple possible
  grant sources. Exercise a spell-backed innate's distinct access and recovery rules.
- Produce reviewed conversion proposals and equivalence fixtures.
- Compare the old C++ behavior with both native-provider and formula-backed calculations.
- Benchmark full evaluation costs and verify preview purity and range quality.

Gate: the pilot covers simple dice, saves, equipment, specialization, shared damage,
target-dependent conditions, per-target randomness, and a timer. All unresolved
semantics are recorded and block the affected integration.

### P3 — Opt-in integration and fallback

- Add explicit server build/startup wiring and the narrow game adapters.
- Integrate verified facts with `spells info` and `skills info`.
- Activate the pilot calculations at their existing numerical call sites.
- Add readiness/timing adapters and an innate information form once its grammar is settled.
- Wire requirement explanations to the same checks as the adopted gameplay gates,
  including explicit native exceptions and source-specific grants.
- Verify uncovered and partially covered abilities through normal commands.
- Exercise safe deactivation, compatible rollback, reload, and relevant saved-state paths.

Gate: normal-entry journeys prove that previews match the selected execution path,
the pilot preserves agreed mechanics, and uncovered abilities retain their supported
behavior. Both persistence builds qualify for the integration they receive.

### P4 — Supported publication and designer workflow

- Deliver durable bundles, atomic activation, conflicts, audit history, and recovery.
- Add before/after previews across levels, specs, equipment, and named target scenarios.
- Include indirect requirement/delegation consumers in the edit-impact report.
- Provide field/condition explanations and a verified authoring walkthrough.
- Test a data change and revert using the same path staff will operate.

Gate: valid updates take effect coherently, invalid or stale updates fail without
partial publication, and a crash or rollback has a demonstrated recovery path.

### P5 — Complete the inventoried scope

- Convert ability families in reviewable batches, beginning with common spell families
  and active skills, then shared/passive mechanics, songs, and player innates.
- Follow shared-effect dependencies rather than duplicating formulas for each class.
- Complete requirement, grant, and recovery bindings for each converted family's
  supported paths, preserving the current source of those rules.
- Include item, NPC, and event callers in each relevant batch.
- Track remaining prose-only effects and verified native providers explicitly.
- Remove superseded runtime math after successful conversion, retaining focused oracles
  as long as they catch an independently meaningful regression.

Gate: every ability/effect in the agreed inventory has a disposition, all required
numbers use shared verified calculations, and every native exception documents its
execution and preview contract. Current Duris grants determine the denominator.

### P6 — Clients and editor

- Add versioned GMCP responses from the same `AbilityInfo` model.
- Discover current DurisWeb authorization, deployment, and editing conventions, then
  implement its formula editor against the established preview/publication service.
- Verify text/client agreement, permissions, stale drafts, publication, and recovery.

Gate: clients and the editor use the shared service and communicate current values,
assumptions, quality, and proposed changes consistently. This completes the planned
Rust-equivalent client/editor capability alongside the C++ framework.

## 13. Worked adoption examples

### Fireball

At the pinned C++ baseline, `spell_fireball` rolls `dice(level / 3 + 5, 6) * 4`,
performs its save, doubles the damage on a failed save, then calls `spell_damage`
with its selected flags. Start with the actual incoming cast level and retain
the save and flag decisions at their existing points.

The definition owns `base_damage` and a parameterized `failed_save(base_damage)`.
Execution rolls the base once. The failed-save calculation consumes that result.
The preview shows the corresponding ranges with their stage and target assumptions.
Tests compare the save placement, roll sequence, final pipeline handoff, and behavior
for player, NPC, and item callers.

### Bash

Start with independently verifiable damage, lag, and recovery facts, including shield
weight and spiked-shield behavior. Then migrate the chance stages using explicit
inputs from the original code. Guard interception, target posture, size, skill
training, takedown checks, and follow-up attacks have their own sequencing.

A partial Bash entry can expose verified facts while its success explanation remains
conditional. Final completion requires the inventory of all numeric stages and their
callers, including the shared takedown helper and any NPC decision probe.

### Timed innate and repeated effect

For a timed innate, derive availability, uses, and rest from read-only state accessors
shared with the execution gate. The actual gate spends a use at its existing point.
For an effect with repeated damage, preserve each tick's original level, actor/target
lookup, RNG draws, and expiry behavior. Reload tests verify which values were captured
earlier and which are intentionally read again.

Duris's Reflection innate is a concrete delegation case. It uses the illusionist's
spell on the user, checks the titan restriction before spending its innate cooldown,
and applies its own lag. Its future info entry must combine the shared Reflection
effect with the innate grant, titan restriction, and innate recovery facts. The
spell's class-learning requirements belong to the ordinary spell acquisition path.

An epic skill is a concrete prerequisite case. Project its existing
`epic_teacher_skill` prerequisite, required proficiency, exclusion, and acquisition
rules into explanations. A reverse index can tell players which epics a skill helps
unlock. Training continues through the existing transaction and confirmation paths.

## 14. Scope, estimates, and decisions to settle during inventory

The full scope is one framework with separate adapters, all inventoried player-facing
ability families, preservation of their existing callers, verified partial fallback,
and the authoring/client tooling needed to maintain it. Existing help prose remains
the general explanation of usage and behavior.

Preliminary effort for one experienced engineer, including review and verification:

- P0-P1, approximately 8-15 working days.
- P2-P3, approximately 8-15 working days for a representative integrated pilot.
- P4, approximately 5-10 working days for publication and operational qualification.
- P5, approximately 15-30 working days depending on actual source divergence and reuse.
- P6, approximately 5-10 working days after inspecting the current clients and website.

These are planning ranges rather than measured delivery times. The Rust design's
46-50-day estimate was a historical estimate for its own architecture. Replace our
ranges after P0 and P2 using measured conversion/review rates and the remaining effect
inventory. The first integrated batch can ship while broader coverage proceeds.

Proposed defaults to validate in P0:

- C++20 implementation using the existing dependency set and JSON catalogs.
- One typed expression core with native escape hatches that have explicit preview contracts.
- Source-controlled baseline plus complete validated runtime generations.
- Preview fallback in the existing info commands and execution selection before mutation.
- Current gameplay as the conversion oracle, with intentional balance changes separately identified.
- Public previews based on the caller and declared target scenarios.
- Pure requirement explanations, grant-source projections, and invocation/recovery
  bindings derived from existing Duris rules, following the feat-system review.

Resolve during implementation discovery the precise innate command spelling, backend
paths for active-generation storage, the first-phase performance budgets, and any
ability whose current behavior depends on undefined or unspecified C++ behavior.
Decisions with observable gameplay or operator-workflow consequences should be recorded
here with the supporting evidence before the affected conversion is activated.

The Luminari review adds rule/binding work to P0-P3 and relationship impact checks to
P4-P6. Include those costs when refining the estimates. Acquisition/grant rule edits
remain explicit gameplay changes, with separately identified equivalence and rollout
requirements. The framework initially exposes the current owners through adapters.

## 15. Reference sources and planning evidence

Local reference paths are relative to this document. The inspected Rust and Luminari
checkouts are recorded at the top of this plan so later changes can be distinguished
from this review.

- [Original tooltip design](https://github.com/moshehbenavraham/duris-rs/blob/4492942d68718fb0443539084d538f922e044b1e/docs/TOOLTIP_DESIGN.md).
- [Formula design and implementation history](https://github.com/moshehbenavraham/duris-rs/blob/4492942d68718fb0443539084d538f922e044b1e/docs/TOOLTIP_FORMULAS_DESIGN.md), particularly arithmetic, roll ordering, ranges, migration, and sections 14-29.
- [Original formula proposal at 3ababc34](https://github.com/Community-Duris/DurisSTDB/blob/3ababc344fa0ae701d25b86bb1e97fb33105f142/docs/TOOLTIP_FORMULAS_DESIGN.md).
- [Current pinned formula design](https://github.com/Community-Duris/DurisSTDB/blob/936261fb247ff78007ef0da1cb88c6b5cb3cd15c/docs/TOOLTIP_FORMULAS_DESIGN.md), at the upstream commit whose tree matches the Rust baseline.
- [Shared formula/tooltip row definitions](https://github.com/moshehbenavraham/duris-rs/blob/4492942d68718fb0443539084d538f922e044b1e/module/src/gamedata/abilities.rs).
- [Compiler and catalog loading](https://github.com/moshehbenavraham/duris-rs/blob/4492942d68718fb0443539084d538f922e044b1e/module/src/engine/formula/table.rs).
- [Execution context and per-use evaluation](https://github.com/moshehbenavraham/duris-rs/blob/4492942d68718fb0443539084d538f922e044b1e/module/src/engine/formula/game.rs).
- [Range evaluation and dependency tracking](https://github.com/moshehbenavraham/duris-rs/blob/4492942d68718fb0443539084d538f922e044b1e/module/src/engine/formula/range.rs).
- [Native custom values](https://github.com/moshehbenavraham/duris-rs/blob/4492942d68718fb0443539084d538f922e044b1e/module/src/engine/formula/custom.rs).
- [Conversion proposal tool](https://github.com/moshehbenavraham/duris-rs/blob/4492942d68718fb0443539084d538f922e044b1e/scripts/formula-codemod.py).
- [Equivalence fixtures](https://github.com/moshehbenavraham/duris-rs/blob/4492942d68718fb0443539084d538f922e044b1e/module/src/engine/formula/parity.rs).
- [Coverage accounting](https://github.com/moshehbenavraham/duris-rs/blob/4492942d68718fb0443539084d538f922e044b1e/module/src/engine/formula/coverage.rs).
- [Data import and conflict handling](https://github.com/moshehbenavraham/duris-rs/blob/4492942d68718fb0443539084d538f922e044b1e/scripts/data-sync.py).
- [Staff preview implementation](https://github.com/moshehbenavraham/duris-rs/blob/4492942d68718fb0443539084d538f922e044b1e/module/src/web/gamedata/preview.rs).
- [Authoring workflow](https://github.com/moshehbenavraham/duris-rs/blob/4492942d68718fb0443539084d538f922e044b1e/docs/CONTENT_EDITING.md).
- [Luminari feat metadata and prerequisite types](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/src/character/feats.h).
- [Luminari feat registration, checks, and generated info](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/src/character/feats.c), especially `feato`, `meets_prerequisite`, `feat_is_available`, and `display_feat_info`.
- [Luminari grant structures](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/src/character/class.h) and [grant processing](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/src/character/class.c).
- [Luminari effective feat and daily-use queries](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/src/core/utils.c), especially `get_feat_value`, `get_daily_uses`, `daily_uses_remaining`, and `start_daily_use_cooldown`.
- [Luminari recovery event registry](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/src/events/mud_event_list.c) and [recovery execution](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/src/events/mud_event.c).
- [Luminari racial invocation table and handler](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/src/act/act.other.c), especially `racial_sla_table` and `do_racial_sla`.
- [Luminari racial feat registration, use, and grant tests](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/unittests/CuTest/test_racial_innate_feats.c).
- [Luminari converted feat prerequisites and cooldown tests](https://github.com/LuminariMUD/Luminari-Source/blob/85fed29152fca9ae5951686827c1e70bd1a22a1a/unittests/CuTest/test_rol_feats.c).
- [Duris epic-skill prerequisite representation](../../src/classes/epic_skills.h).

This plan was prepared from source, the historical proposal, current implementation
notes, existing Duris browser tests, and the Luminari feat-system review above. No
framework code, game configuration, or production state was changed during planning.
The milestone gates above describe future acceptance work and do not claim completed
runtime qualification.
