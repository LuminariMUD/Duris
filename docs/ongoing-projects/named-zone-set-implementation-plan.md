# Named zone sets: delivery plan

Deliver [#706](https://github.com/LuminariMUD/Duris/issues/706) as one integrated
feature and one review target. Continue the existing implementation.

**Execution scope:** integrate the feature, finish the focused proof and review,
and deliver one PR. Production deployment remains a separate owner operation.

## Outcome

Every reviewed eligible area produces named equipment with a durable zone ID,
correct matching-piece bonuses, safe removal, and an accurate `namedreport`.

- Use the [assignment document](named-zone-set-first-pass-assignments.md) as the
  roster and threshold authority: **298 sets, 389 tiers, 106 effect IDs**.
  This retains 115 existing sets and adds 183 (104 original choices plus 79 wider
  additions). The reviewed 354 active records include 56 documented exclusions.
  Keep those decisions; reopen an entry only for a concrete error.
- Preserve existing reviewed effects, thresholds, class/alignment restrictions,
  light/darkness exclusions, cooldowns, and capped invocation levels. New rows
  keep their assigned single tier and three-, five-, or six-piece requirement.
- Preserve matching-set HP: `5 * (pieces - 2)` from two pieces onward, with zero
  below two. Preserve the worn-armor driver, weapon contribution, excluded belt
  attachments, and ordinary gear HP cap.
- Keep named-drop probabilities, item-affect rolls, weapon procs, and roaming
  spawn selection unchanged. Set definitions remain separate from spawn rows.

**Non-goals:** another roster/balance study, new effect families or tiers,
general-purpose effect/persistence frameworks, new storage services or switches,
unrelated refactoring, a new test framework, or another PR stack.

**Files:** reuse `src/item/named_sets.*`, `named_set_origin.*`, `named_set_effects.*`
and their existing generator, wear/affect, persistence, report, help, and authored
area callers. Extend the existing `tests/async/test_named_set_*.py` and
`run_named_set_*_journey.py` tests where a required case is missing. The
[effect inventory](named-zone-set-effect-inventory.md) is reference material,
not a request to redesign the effect system.

## Remaining work

### 1. Integrate once

Use the accumulated implementation on `branch/named-zone-set-rollback-proof` and
bring it into `branch/named-zone-set-expansion` for one final PR against `master`.
Check current branch heads before integration; preserve later fixes and unrelated
work. Keep existing commits and branches intact. Do not replay development from
the original planning commit or propagate every change through the old PR stack.

The following existing repairs are absent from the inspected accumulated head;
include them, or their verified equivalents, without implementing them again:

- `3a4b0ed26`: validate origin metadata only for items the loader keeps.
- `79dcb93e6`: apply Vitality's HP adjustment before evaluating body position.
- `79ba081c3`: preserve the Crown's independent regeneration.
- `b0ffc0342`: prove real dispel traversal cannot remove named cooldowns.
- `0cbfd9794`: suppress ineligible automatic Guardian Spirits attempts.
- `2a482448e`: require fresh captured output for each report-cache state.

Reconcile the final diff with current `master` once. Address concrete review
findings on that integrated branch. Superseded PRs should point to the single
replacement when the integration work is authorized; branch cleanup is not a
prerequisite for proving the feature.

### 2. Close the known Armor proof gap

Update [run_named_set_transfer_journey.py](../../tests/async/run_named_set_transfer_journey.py)
to measure ordinary Armor alone with identical equipped item contributions and
cast strength, then compare the ordinary-plus-set state against that independent
value. Check removal, re-equipping, and reload. The current overlap-to-overlap
comparison can pass even when Armor incorrectly stacks.

Use the existing `NamedSetGame(runtime=..., binary=...)` support with a fresh
private copy. The retained runtime is `bin/tests/named-set-roster-world`; its old
transfer manifest contains missing container references. Prepare valid test
containers in the copy. Preserve the original items, UIDs, journals, and failure
evidence. Do not reset the original runtime or recreate missing UIDs.

If this test exposes a product defect, fix its existing owning path and rerun the
affected regression. Add no product machinery merely to make the test easier.

### 3. Prove the integrated result

Run one final focused pass after integration. Reuse completed native journey
results where the relevant implementation and setup are unchanged. Repeat a
journey only for a changed dependency, an actual failure, or missing evidence.
Use the existing logs and result JSON under `bin/tests/named-*`, matched to the
source revision and runtime they actually prove.
Record results and remaining limitations in the final PR; create no new tracker.

The required proof is:

- **Catalog and eligibility:** all assigned rows and original definitions agree
  with the roster; reject duplicate/missing zones, unsupported effects, and
  unreachable thresholds. Keep stale IDs #30/#250 inactive. Retain the authored
  naming fixes for #204/#990 and existing sets #87/#370/#676/#824.
- **Identity and persistence:** new gear uses the stored zone ID. Unique legacy
  tags resolve exactly, including revealed weapon suffixes; ambiguous/retired
  tags retain their legacy HP group but gain no guessed zone spell. Malformed
  metadata follows the established load-error policy without silently dropping
  items. Cover Ceothia #808/#811/#814, Underworld #44/#300, Braddistock #13/#1350,
  Tiamat #196/#199, and historical Misty Vale origins. Retain full/incremental
  save and reload evidence for both MariaDB and flat-file storage, nested
  transfers, player/pet/corpse/locker/chest/shop/world items, and edits/clones.
- **Effects:** actual grants and derived character benefits match the thresholds;
  two different sets and two sharing a spell remove only unsupported benefits
  when either set is removed.
  Ordinary casts in both orders retain their own duration and do not stack with
  the set. Expiry, dispel, re-equipping, and driver swaps preserve cleanup and
  cooldowns. Reuse the existing native handler/class/level qualification.
- **Gameplay:** exercise eligible named drops, report output, worn benefits,
  removal, and save/reload for Bloodstone Keep (#740), The Forgotten Forest (#827),
  and Tharnadia (#1325). Tharnadia gives no set bonus at two pieces, Armor/+5 HP at
  three, and Armor/Endurance/+15 HP at five. Retain the focused identity/title
  journeys above; do not repeat every storage journey for every zone or effect.
- **Publication:** cached and uncached reports show the complete identical
  roster, IDs, thresholds, restrictions, pagination, and cooldown markers.
  Verify cold/warm/unavailable Redis, expiry, boot warming, and invalidation
  through the existing cache test. Canonical help must agree on both backends.

Run the existing focused checks once on the integrated result:

```sh
python3 tests/async/test_named_set_catalog.py
python3 tests/async/test_named_set_origin.py
python3 tests/async/test_named_set_membership.py
python3 tests/async/test_named_set_effect_ownership.py
python3 tests/async/test_named_set_effect_levels.py
python3 tests/async/test_named_set_cooldowns.py
python3 tests/async/test_named_set_report_cache_live.py
python3 tests/async/test_random_equipment_golden.py
python3 tests/async/test_random_mob_theme_runtime.py
./scripts/format.sh --check
make -C src PERSISTENCE_BACKEND=mariadb
make -C src PERSISTENCE_BACKEND=flatfile
```

Rerun the existing MariaDB player/pet regressions affected by the loader repair,
the corrected transfer journey, and the native wear cases affected by integrated
spell fixes. Use the existing wear/report runners for the final gameplay check.
Add a persistence test run only where the changed path or missing evidence calls
for it. Build once per backend after the final C/C++ edit, not after each proof.
Regenerate authored area changes with `make world` in the isolated runtime when
needed. Keep databases/runtimes local, artifacts under `bin/`, and generated
world/player data out of commits. CI is not a required wait.

### 4. Finish review and handoff

- Resolve outstanding review findings using the integrated code and evidence,
  including the existing cooldown-dispel proof and corrected Armor comparison.
- Remove stale pending-work claims in the companion documents. Keep the final
  roster, thresholds, restrictions, and brief player-facing help/release notes.
- Refresh the existing 115-row compatibility checkpoint in
  `bin/tests/named-set-rollback-source` with the integrated safety fixes.
  Use `run_named_set_rollback_journey.py` once on a copied runtime
  to verify downgrade/re-upgrade preserves origins and item graphs, removes
  unsupported transient effects, and refreshes reports. Reuse the existing
  compatibility path; do not build a new rollback system or rewrite old tags.
- Provide one reviewable PR against `master`, exact local validation results,
  and the remaining deployment steps for #706. Production publication uses the
  existing deployment workflow with explicit owner permission. Report it as
  pending until it actually happens; never imply this plan rewrite deployed it.

## Stop rule

Implementation is ready when the roster and required behaviors are present in
one reviewed integration, the focused checks pass, required gameplay/persistence
claims have valid evidence, and the compatibility/help handoff is complete.
Keep merge, issue closure, and deployment status explicit. Do not mark #706
complete while an acceptance criterion is missing.

Once those conditions hold, finish. No additional hardening phase, expanded
matrix, extra review stack, or repeat green suite without a specific changed
requirement, failing case, or unresolved review finding.
