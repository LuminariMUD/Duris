# Ival: focused delivery plan

Replanned 2026-11-10 at the user's request: finish the agreed ival outcome with
direct implementation, bounded verification, and no continuing hardening detours.
Implementation and qualification are **complete**, ready for review in the linked
stacked PRs. This file is the delivery and verification reference; the original
review, source evidence, and 22 chunk records are preserved in
[review history](ival-system-review-history.md). Its old queues are superseded.

## Outcome and scope

One consistent, explainable, numerically safe valuation for authored and generated
items, shared by server/editor/report, with correct economic consumers and proven
preservation of valuation inputs through **MariaDB** persistence. Proc semantics,
diagnostics, inspection/index work and the real journeys below are qualified.
New balance coefficients remain separate reviewed policy work. Deployment is a
separate authorized operation. Flat-file server persistence is unsupported.

## What already exists — reuse it

- Shared numeric evaluator, runtime and normalized-template adapters, editor
  estimates with four-slot/B5 preservation, and full-context offline reporting.
- F01–F04 circle, packed-average, apply-order, zero and duplicate repairs;
  F08 numeric/config/property bounds and unavailable-score admission; F14 shared
  material quantities and checked XP; F15 dead reset/recovery work removal.
- Published implementation through [#989](https://github.com/LuminariMUD/Duris/pull/989),
  stacked on #987/#982/#981/#978. Publication does not mean every PR has merged.
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
about 9.85–10.74%, without quest-floor/count changes. D actually forges this newly
eligible item at level 37 and verifies rejection at level 36.

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

**Complete:** qualification spans #987 and #989. Startup fix `f3ef35689`
is review-ready in [PR #987](https://github.com/LuminariMUD/Duris/pull/987) (bug label).
The existing disposable
MariaDB item-instance journey exposed minimal/no-specials enhancement admission
and template-cache startup regressions. The fix distinguishes an intentionally
absent index from a failed rebuild and caches the already-parsed templates in every
boot mode. The same real MariaDB journey now passes essence commands, relog/restart,
stored instance fields, and cap rejection without currency/material loss. Preliminary
evidence is in `ival-evidence/f16-mariadb/preliminary.json`. No live DB/player
state is used.

**Valuation lifecycle bundle passed:** `tests/async/run_ival_system_journey.py`
extends the existing full-world/disposable-authority helpers. The same eight
generated, essence/superior-enhanced, fourth-slot, duplicate, native-proc, packed
glove and B5 items retain their UIDs, indexed applies, valuation fields and actual
in-game Lore scores through save/rent/relogin, server restart, locker storage with
restart/retrieval, and real player death with corpse restart/recovery. Real essence
and superior commands also charge the expected 1000 and `1000 + 100 × source ival`
copper respectively in this frozen configuration. Binary/formula/config hashes,
initial fields/scores and the five passed gates are in
[valuation-bundle.json](ival-evidence/f16-mariadb/valuation-bundle.json).
The run uses an isolated full world under POSIX `/tmp` and a fresh loopback MariaDB
10.11 schema; its private bank is also an inn for actual mortal rental. Fixture
corrections use real rental, door-opening and carry limits rather than changing
the server to accommodate the test. Python compilation and the real journey pass.
**Craft/Forge qualified:** `bca0024f2`,
[PR #989](https://github.com/LuminariMUD/Duris/pull/989) (bug label),
`branch/ival-economic-qualification`, stacked on #987.
The real Forge-first migration-file test failed with "You dont know any recipes
yet" because Forge bypassed the existing shared provider. Its only server change
is to call `crafting_get_player_recipes`, matching Craft's SQL-first import,
deduplication and eligibility policy. The same run now passes; invalid/quest
targets stay out, and a later migration-file edit cannot override SQL ownership.
Both commands reject #99432 at level 36 without changing any item, coin or XP.
At level 37 it is actually forged at value 111, consuming exactly 23 high silver
and one flux. The two other successful transactions cover value-8 Craft and a
value-29 B5 magical Forge, including tool/essence consumption. Previews, delivered
scores and XP match; nominal XP 8000/29000/111000 becomes 16000/58000/222000 with
the observed well-rested multiplier of 2. Currency is unchanged. The full eight-item
lifecycle bundle also passes after these commands. Evidence:
[craft-forge.json](ival-evidence/f16-mariadb/craft-forge.json). Server build,
recipe-provider contract, Python compilation and real MariaDB journey pass.

**Final corpus/report passed:** [f16-integration](ival-evidence/f16-integration/),
against the same `c0b82df5e` pre-semantics baseline as B. All 19,334 effective
templates and 8,720 generated samples retain constructor/template/CLI parity;
only #99432 changes (338 → 111), with no generated deltas. Report provenance,
read-only evaluation and missing/invalid-context failure status pass. The measured
salvage 5/10/15/20 and quest-floor crossings remain zero; the one recipe admission
and regular-bag 125 crossing and zone-weight effects match B's recorded cohort.
Nominal composition remains separate from scaled costs and economic scarcity.

**Quest reward journey passed:** the existing focused MariaDB reward scenario
passes level-11 ASK, level-30 KILL and level-31 KILL with a bonus root (1/1/2 items),
including completion state and reward UID preservation after restart. It uses
seven real boots and a fresh schema without requiring any `quest_zone=1` rows.
The existing probe controls route, level, quota and bonus rolls for reproducibility;
production valuation, reward execution, SQL authority and restart remain active.
The private POSIX world's object/room hashes exactly match the final shipped-world
report. Evidence: [quest-rewards.json](ival-evidence/f16-mariadb/quest-rewards.json).
Reproduce with `python3 tests/async/run_ival_system_journey.py --quest-rewards`.

**Final item commands and lifecycles passed:**
[commands-and-lifecycles.json](ival-evidence/f16-mariadb/commands-and-lifecycles.json)
records ten passed gates with `complete=true`. The same run covers all eight
salvage values 5/6/10/11/15/16/20/21, recovering the expected material grades.
Seven deliberate cheap-item breakages at value 5 consume only the source and
retain unused tools before the successful recovery. Scientific-tool consumption,
one/two material outputs and optional recipe/essence outputs are accounted for.
Real regular/rare/exceptional bags deliver values 79/470/54 within their respective
125/25/50 cohorts; overfull-inventory rejection preserves every item, coin and XP.
Bag openings occur as a mortal; existing exact UID selectors and temporary staff
Lore inspection handle arbitrary reward keywords/NOIDENTIFY, then restore level 37.
After these commands, the same eight item classes preserve their fields, UIDs and
scores through relog, restart, locker store/restart/retrieval and real death with
corpse restart/recovery. Both final MariaDB evidence scopes use binary SHA-256
`2dfe4f4cc8ca416cf20331c43a08d58ecccec6d997511927cf0aff6d871b714e`.

The completion audit below has no remaining implementation gate. Earlier
`preliminary.json`, `valuation-bundle.json` and `craft-forge.json` retain their
historical partial-scope flags; the two completed evidence scopes above supersede
those flags for final qualification. Unsupported weights and balance decisions
remain the explicitly separate policy work described in this plan.

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
- F05/F09: B. F06: shared editor arithmetic and B's qualified estimate/status parity.
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

## Completion audit

The current tree was checked against F01–F16, including their original acceptance
criteria in the archived review. Every implementation gate below has retained proof.

- **F01–F04:** `get_mincircle` and the shared numeric evaluator implement full
  class/spec bounds, fractional packed means, canonical multiplier composition,
  neutral zero modifiers and widened duplicate totals without rewriting slots.
  Native sanitizer characterization and the per-slice reports in `f01`, `f02`,
  `f03`, `f04-zero` and `f04-duplicates` retain every changed threshold cohort.
- **F05/F09/F11:** the explicit proc policies, all-five-bank coverage and shared
  evaluator/runtime adapter/header are byte-identical to qualified batch B
  (`0f7e12253`, LF-normalized comparison). Its mapping/route/67-priced-bit fixtures
  and reconciled staff/report breakdowns remain applicable. Utility overrides,
  unclassified and unsupported inputs are explicit; unresolved aggregate native
  strengths retain their declared incomplete status rather than new coefficients.
- **F06:** editor arithmetic, view and search are also unchanged since B. Retained
  common-input server/editor, four-slot, B5 I/O and actual search fixtures pass;
  normal/debug maintained editor builds are recorded in the history. Missing
  native/racial/specialization context remains an explicitly labeled estimate.
- **F07/F14:** the final native/CLI report proves all 19,334 effective templates,
  8,720 generated samples, configured provenance, read-only evaluation and failed
  missing/invalid-context publication. Existing writer I/O failure qualification
  is retained. Checked quantity fixtures cover fractional/large bounds; actual
  Craft/Forge and superior commands verify quantities, coins and nominal versus
  credited XP. Report identity composition remains nominal and unscaled.
- **F08/F10:** sanitizer bounds/config/property fixtures, explicit unavailable
  admission, and minimal-world startup qualification remain applicable. Real
  level/recipe rejection conserves inventory, wallet and XP; essence cap rejection
  conserves currency/materials after restart. The two real enhancement fees agree
  with the configured copper contract; inert sections and undefined rows were removed.
- **F12/F13/F15:** `f12-consumers` records normalized catalog/index parity, atomic
  failure/tie/duplicate cases, zero inspection identities/RNG/events, scoped timings,
  and one locker valuation per object. Native bag empty/read/delivery failures
  preserve their source; reset/recovery tests preserve outcomes and RNG. The real
  locker store/restart/retrieval bundle independently preserves inputs and scores.
- **F16:** the complete eight-class lifecycle, Craft/Forge, all eight salvage
  boundary cases and three faerie-bag cohorts pass in the same item fixture, with
  rejected-operation conservation. The final corpus and three real quest reward/
  restart cases also pass. Completed evidence is linked above; every changed
  score/threshold cohort remains explained in its per-slice report.

Reproduction on this NTFS worktree uses an LF-normalized copy of the existing
disposable-DB wrapper under `bin/tests/ival-disposable-mariadb.sh`, followed by
`python3 tests/async/run_ival_system_journey.py`. The separate `--quest-rewards`
mode creates its own disposable MariaDB authority and private POSIX world. Neither
mode reads checkout credentials or operates on a running game. Reuse the final
corpus report after these test-only additions; no server/evaluator source changed.

## Handoff

Local: `C:/Users/apexw/.codex/worktrees/ival-system-improvements/duris`.
Remote: `duris-staging:/home/staging/duris-worktrees/ival-system-improvements`.
Current branch: `branch/ival-economic-qualification` for D (#989), based on
`branch/ival-qualification` (#987), then `branch/ival-consumers` for C (#982).
Both worktrees receive the committed final qualification. A–D are implemented and
qualified for review. Read-only template views deliberately omit native runtime-state initialization;
eligibility/score parity is qualified, rather than unrelated money/state slots.

Current formula: `ival-v8-proc-semantics`. Archive/evidence links above preserve
baseline revisions and earlier PRs. Read the relevant historical finding when
needed; the archived queues are superseded. No implementation acceptance gate
remains. The next step is review of the published PR stack; merge and deployment
are separate operations. Reuse the completed evidence unless a relevant source
change or failure justifies another run.

### Operator and player notes

The current formula is `ival-v8-proc-semantics`; qualifying binary/config hashes
belong to their recorded evidence run. Before an authorized deployment, retain the
previous binary, configuration files and formula identity together. Restart after
valuation configuration changes so template inspection, enhancement indexes and
quest reward profiles all use the same context. A failed index rebuild disables
the affected consumer until restart; do not treat a partial catalog as current.
Rollback must restore a matching binary/configuration set and rebuild those
indexes/profiles by restarting. Recalculation and rollback do not reverse completed
crafting, salvage, enhancement or reward transactions in MariaDB. No production
deployment, database migration or player reimbursement is part of this delivery.

For players, enhancement fees now display the amount actually charged. Item value
includes the corrected stored applies and executable proc policy; the newly eligible
Zarthos claymore (#99432) has value 111 and requires level 37 for its modern recipe.
These are calculation fixes, with no new proc-strength coefficients. Staff/report
breakdowns identify unsupported or incompletely classified effects rather than
assigning them invented prices. Final economic and persistence qualification is
recorded above; no deployment or balance-coefficient change was performed.
