# Ival: focused delivery plan

Replanned 2026-11-10 at the user's request: finish the agreed ival outcome with
direct implementation, bounded verification, and no continuing hardening detours.
Implementation is **incomplete**. This file is the active work queue; the original
review, source evidence, and 22 chunk records are preserved in
[review history](ival-system-review-history.md). Its old queues are superseded.

## Outcome and scope

One consistent, explainable, numerically safe valuation for authored and generated
items, shared by server/editor/report, with correct economic consumers and proven
preservation of valuation inputs through **MariaDB** persistence. Finish the
remaining proc semantics, diagnostics, inspection/index work, and real journeys.
New balance coefficients remain separate reviewed policy work. Deployment is a
separate authorized operation. Flat-file server persistence is unsupported.

## What already exists — reuse it

- Shared numeric evaluator, runtime and normalized-template adapters, editor
  estimates with four-slot/B5 preservation, and full-context offline reporting.
- F01–F04 circle, packed-average, apply-order, zero and duplicate repairs;
  F08 numeric/config/property bounds and unavailable-score admission; F14 shared
  material quantities and checked XP; F15 dead reset/recovery work removal.
- Published implementation through [#982](https://github.com/LuminariMUD/Duris/pull/982),
  commit `3253eddfa`. Publication does not mean every PR has merged.
- Native evidence: 19,334 effective templates; 8,720 seeded generated items in
  formula-delta runs; 2,649 unchanged shipped property values. Results apply to
  their recorded revisions, not automatically to future changes. Durable results
  are in [ival-evidence](ival-evidence/) and the history.

These completed changes are not a reason to start another config, integer-width,
XP, parser, or persistence-framework audit. F08's remaining acceptance is checked
in the actual consumer journeys below; reopen a boundary only for a concrete
failure of those requirements.

## Execution rules

1. Work through A → B → C → D. Finish the current batch before starting another.
   A batch may contain a behavior-preserving commit and a behavior-changing commit;
   publish a focused labeled PR when that batch is ready, stacked as needed.
2. A new change must name the acceptance requirement below that fails without it.
   Trace/probe that path only. An unverified suspicion is not a new prerequisite.
   Fix blockers in the batch; record unrelated confirmed defects separately for
   follow-up without interrupting this delivery. This replaces the earlier broad
   instruction to pursue every discovered issue during this project.
3. Reuse existing modules, fixtures, report mode and journeys. No new service,
   rule engine, generic metadata framework, test framework, score cache, config
   surface, hot-reload system, or persistence rewrite.
4. Extend a test only for a changed behavior or missing acceptance case. Run the
   focused test, required formatting/build, and relevant journey. Once green,
   commit and advance. Repeat only after a relevant change, failure, or unresolved
   concern. Documentation edits do not trigger a server build or corpus rerun.
5. Run one effective-world/generated delta report per formula-changing batch,
   then a final integration report. Preserve prior evidence instead of repeating
   it after unrelated presentation/config edits. No routine full-suite burn-ins
   or CI waiting; required local checks and review still apply.
6. Keep updates here to status, commit/PR, proof, and next action. No new narrative
   chunk log per helper. Report completed batches and named blockers; do not repeat
   a finish ETA without measured remaining work supporting it.

## A — publish the existing enhancement patch (F10)

**Complete:** `a2860a3aa`, [PR #978](https://github.com/LuminariMUD/Duris/pull/978)
(bug label), stacked on #977. Exact displayed/debited currency, removed inert
spell/undefined-flag rows, and retained unsupported-section diagnostics. Native
sanitizer enhancement tests, related contracts, server build and format/tidy
checks passed. Existing results were reused after the plan-only revision.

## B — finish valuation semantics and explanation (F05/F06/F09/F11)

**Review-ready:** `527ad4c40` + `0f7e12253`, [PR #981](https://github.com/LuminariMUD/Duris/pull/981)
(bug label), `branch/ival-semantics`, stacked on #978. The 321 unique mappings retain first-match prices, with
90 explicit utility policies. Twenty callbacks proven to use the common melee-only
gate lose inactive credit on packed non-backstab weapons; backstab, periodic and
invoke routes retain credit. Unsplit legacy native prices are labeled incomplete
when normal melee is suppressed, rather than assigned invented replacement weights.
Sparse slots, missing callbacks, invalid gloves and configured artifacts 21/22
match dispatch; instance proc-library bridges no longer reprice plain siblings.
Staff output and `item-values.csv` expose terms, checkpoints and unpriced coverage.

Native characterization/67 priced-bit coverage, weapon/artifact/sword/monk and
enhancement fixtures, report I/O, server and maintained editor builds pass.
The exact-parent comparison against `c0b82df5e` covers **19,334 templates + 8,720
generated samples**, with one changed template and no generated changes. Native
constructor/template and actual CLI parity, provenance, reconciled report rows
and read-only evaluation pass. Evidence: [f09-procs](ival-evidence/f09-procs/).
Item **99432: 338 → 111**; minimum level 113 → 37, recipe admission 0 → 1,
high/low units 68/2 → 23/0, XP 338000 → 111000, nominal superior fee 34800 → 12100
copper. It crosses the faerie-bag 125 ceiling; zone 994 unit-fit quest weights fall
about 9.85–10.74%, without quest-floor/count changes. D must exercise this newly
eligible authored item in its shared command/persistence fixture bundle.

**Files:** existing `src/item/item_value*`, the proc chain in
`src/economy/tradeskill.c`, relevant packed/native dispatch, existing staff/report
presentation, and their native fixtures. Keep one numeric evaluator.

- Extract proc policy into a small explicit table, preserving first-match legacy
  values and removing duplicate mappings. Give every effective bound callback a
  known policy or explicit unclassified status, including generic/proc-library
  bindings. Replace the negative utility sentinel with an explicit override.
  Reuse the binding catalog and existing mapping; unclassified status does not
  require researching or pricing every individual callback.
- Credit effects that actually execute: packed/native coexistence, artifacts
  21/22, legacy sparse slots, and invalid/gapped monk gloves. Retain valid native
  periodic/invoke effects; do not invent new proc strengths. Settle existing
  prototype/instance proc-library mutation semantics so later indexes have a
  stable, declared context. Prove routing at the shared weapon/glove dispatch
  boundaries; do not open a per-proc combat-effectiveness investigation.
- In the existing breakdown/report, expose base and multiplier contributions,
  overrides, ignored/unsupported inputs, context completeness and final score.
  Classify current generated/eligible inputs across all five banks, applies and
  types as priced, intentionally zero, temporary, unsupported or special policy.
  Include shield/ranged terms, omitted racial/KARMA applies and scripted/dynamic
  effects. An explicit unsupported diagnostic satisfies coverage; guessing a
  weight does not. Existing priced inputs need meaningful fixtures.
- Preserve common-input editor/server parity, four slots, and explicit estimate
  semantics in both editor view and search. Extend existing presentation only as
  needed to expose those same statuses; do not build a new inspector application.

**Done:** unique proc mappings; utility override independent of other stats;
non-executing packed effects receive no credit; native coexistence cases pass;
all current input families have a declared treatment; breakdown reconciles to
the returned value. Evaluations preserve inputs, RNG, UIDs, events and object
counts. Qualify the batch's changed scores/thresholds with the existing native
corpus and generated-sample runner before publication.

## C — finish the existing consumers (F12/F13/F15)

**Review-ready:** `3253eddfa`, [PR #982](https://github.com/LuminariMUD/Duris/pull/982)
(bug label), `branch/ival-consumers`, stacked on #981. Inspection uses borrowed normalized template views; actual
grants instantiate only selected results. Index publication is atomic, duplicate
apply locations are indexed once, and tier queries use aggregate totals while
retaining stored-slot caps. Existing radius/distance and tie preferences remain.
Bag selection is bounded/uniform over eligible vnums and preserves the source on
empty/missing/delivery failure. Locker sorting values each object once and retains
the legacy tie order and chest boundaries. Existing property application refreshes
both index and quest reward caches; failed rebuilds disable the affected consumer
until restart. Proc-library instance changes do not reprice sibling templates.

Native qualification against `946573801` preserves all **9,083** indexed vnums,
hash chains and ties, across **19,334** constructor/template/eligibility comparisons.
Index transient identities: **16,972 → 0**; new inspection RNG/event/object deltas
are zero. Warm-cache index time: **916733 → 8611 microseconds**; stat entries:
**12432 → 12422**. These timings exclude cold template-cache population.
Evidence: [f12-consumers](ival-evidence/f12-consumers/). Focused sanitizer cases
cover atomic allocation/template failures, duplicate tiers, bag failures/ranks,
property journeys and locker empty/single/tied/10000-item lists; the latter uses
exactly 10000 value calls (~1.7 ms with a controlled score endpoint).
Quest catalog/republication and enhancement contracts pass. Native CLI parity and
report checks pass; formula stays v8 and B's generated-sample evidence is reused.

**Files:** enhancement index/planning, world-quest profiles, faerie-bag selection,
locker sorting, and the specific stale valuation descriptions. Reuse the existing
normalized `object_template` adapter and boot context.

- Iterate actual templates with range/eligibility filters for enhancement indexes
  and quest profiles. Read original/target/material metadata without constructing
  temporary items. Instantiate a selected grant only when needed.
- Use `MAX_OBJ_AFFECT`; index each semantic stat once after duplicate aggregation.
  Preserve replacement and superior tie policies. Make partial index construction
  fail/report explicitly. Remove or give the existing attempt limit an actual
  bound on work; do not add another search setting or change reward preferences.
- Bound faerie-bag no-candidate work, preserve uniform eligible-vnum selection and
  the bag on failure. Confirm absent templates and failed candidate loads terminate.
- Compute each locker object's value once per sort; preserve ties, links and chest
  boundaries. Correct stale logarithmic/load-policy descriptions. Measure the
  affected load/evaluation counts and representative timings once; expand no
  performance work beyond these identified paths.

**Done:** no inspection-only UID/event/object-count changes; normalized catalog
scores agree; duplicates, ties, collisions, empty ranges, allocation/load failure
and no-result cases pass. Locker empty/single/tied/large cases retain every object
once with one valuation each. Boot indexes and quest profiles share B's stable
context; any supported later context mutation updates dependent consumers before
publication. Use the existing lifecycle path, not a general invalidation system.

## D — qualify and hand off the integrated result (F07/F08/F14/F16)

**Start with the existing MariaDB journey setup.** Verify dev/staging identity and
reuse its command/persistence harness. Extend fixtures and assertions only.

- Freeze source/formula/config/context for each journey. Assert inputs and score
  before/after save/logout/login, locker storage/retrieval, corpse recovery and
  restart. Cover generated, essence-enhanced, superior-enhanced, fourth-slot,
  duplicate-apply, native-proc, packed-glove and B5 items. Carry one small fixture
  bundle through these lifecycles; do not create separate suites for every item.
- Exercise craft/forge, salvage, enhancement and reward boundaries: preview matches
  currency charged, XP awarded, consumed materials and delivered result; invalid arithmetic
  and rejected/no-result operations preserve inputs. Use existing checked helpers.
  Check real recipe import/provider behavior, not source-string contracts alone.
- Run the final effective-template/generated report. Explain salvage 5/10/15/20,
  craft/forge player/recipe, enhancement source/donor/result, quest floor/zone-weight
  and faerie-bag 25/50/125 crossings; include quantities, XP/currency, classifications
  and outliers. Keep nominal unscaled report composition distinct from configured
  costs or economic scarcity. Verify report provenance, parity and failure status.
- Run focused executable checks and required build/format gates for final touched
  code; build maintained editors if touched. Record real MariaDB evidence separately
  from native/stub evidence. Publish concise operator/player notes and review-ready
  PRs. No completed claim while a required journey remains unrun.

**Done:** every required outcome above has current evidence, each changed threshold
cohort is explained, and review artifacts are published. Rollback notes retain
binary/config/formula identity, rebuild indexes/profiles consistently, and state
that recalculation does not reverse completed economic transactions. Deployment,
balance tuning and reimbursement are separate decisions.

## Requirement coverage and verification reuse

- F01–F04: implemented; retain characterization and prior corpus evidence.
- F05/F09: B. F06: implemented editor sharing plus B's remaining status/parity.
- F07: implemented offline context plus D's final report verification.
- F08: implemented bounds/config/property fixes plus D's concrete command admission.
- F10: A. F11: implemented shared owner/template adapter plus B's detailed breakdown.
- F12/F13: C. F14: implemented quantity helper/report semantics plus D's journeys.
- F15: implemented reset/dead-work removal plus C's locker/description work. F16: D.

Reuse `test_item_value_characterization.py`, `test_monk_glove_tools.py`,
`test_enhance_ival_runtime.py`, `test_item_value_template_runtime.py` (supports
`--numeric-baseline REF --delta-output DIR`), existing quest/crafting/SQL codec
tests, and actual MariaDB journeys under `tests/async/`. Run only those affected
by the batch. Codec/source-contract tests alone never prove a persistence journey.

## Handoff

Local: `C:/Users/apexw/.codex/worktrees/ival-system-improvements/duris`.
Remote: `duris-staging:/home/staging/duris-worktrees/ival-system-improvements`.
Latest batch: `branch/ival-consumers` for C (#982), based on `branch/ival-semantics` (#981).
Synchronize committed work to the remote worktree. A–C are implemented; D remains
open. Read-only template views deliberately omit native runtime-state initialization;
eligibility/score parity is qualified, rather than unrelated money/state slots.

Current formula: `ival-v8-proc-semantics`. Archive/evidence links above preserve
baseline revisions and earlier PRs. Read the relevant historical finding when
needed; do not reload the entire archive or restart the audit. The next
implementation action is D: use the existing dev/staging MariaDB journey setup,
carry the shared fixture bundle through actual commands and persistence lifecycles,
and record final integration/operator evidence. Reuse A–C's completed qualification.
