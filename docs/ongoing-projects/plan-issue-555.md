# Issue #555: refill missing shop stock after a normal reboot

Status: implemented and locally qualified; review stack is ready. Updated 2026-11-01.

## Resale review fix

PR #562's review exposed a paid resale purchase that printed success but lost
the item: its preserved UID already existed in custody, while the SQL checkout
submitted it as a new creation. Finite SQL checkout now moves the existing object
directly to the player, following the accepted memory-authority persistence rule.
Payment and delivery happen in the same game-loop call. The shop's outgoing
snapshot is queued before the buyer's snapshot, retaining the existing crash
policy rather than introducing a new transaction or minting a replacement UID.

Shop snapshots now claim their saved graphs through the same SQL claim writer as
other owners. Restoration filters superseded shop rows against custody, promotes
retained contents past stale containers, and checks duplicate UIDs only after
filtering. Legacy resale custody that still names the seller is accepted only
when that seller's saved inventory no longer contains the UID. An unavailable
legacy-ownership query aborts restoration without publishing a partial catalog.
No migration or production operation is needed.

Focused validation passes: 21 ASan/UBSan SQL population/restore scenarios;
`run_player_save_claim_mysql.sh` on disposable MariaDB, including shop graph
claims replacing the seller's custody; the production shop save/flush runner;
dirty-shop retries; player-save claim checks; live flat-file route contracts;
both backend builds; Python compilation; formatting and whitespace checks.

The extended reboot-stock gameplay journey verifies that legacy resale survives,
an ordinary paid repurchase delivers its original UID, saving does not charge
again, and an insufficient-funds refusal leaves stock and wallet unchanged.
Its MariaDB and flat-file legs pass, including the existing refill, repeated
reboot, native copyover, SIGKILL and clean-stop recovery controls. The final
MariaDB rerun against the stale-duplicate ordering fix also passes.
Final qualified binary SHA-256 values: MariaDB
`720b0801a29e27e1a84ad10c3f7051fe43e8e2a15a96b8f3f85ec425ee1c170e`;
flat-file
`f64148e097ca71698d594121c636e0235c54d11053e70a82dd8400598aaed6ca`.
Evidence is under `bin/qualification/resale-fix-*.json` and accompanying logs;
the checks and build logs use the `bin/resale-fix-*` prefix.

```sh
python3 tests/async/test_shopkeeper_population.py
bash tests/async/run_player_save_claim_mysql.sh
python3 tests/async/test_shopkeeper_save_runtime.py
python3 tests/async/test_dirty_shopkeeper_retry.py
python3 tests/async/test_player_save_claim.py
python3 tests/async/test_shop_trade_live_route.py
bash tests/async/with_disposable_mariadb.sh python3 tests/async/run_shop_reboot_stock_journey.py --backend mariadb --server bin/server/dms_new --report bin/qualification/resale-fix-mariadb-final.json
python3 tests/async/run_shop_reboot_stock_journey.py --backend flatfile --server bin/server/dms_resale_flatfile --report bin/qualification/resale-fix-flatfile.json
```

The qualification below predates this review fix; its original binary hashes
remain historical evidence for that earlier implementation.

- Issue: [#555 — reboot-only shop stock is discarded](https://github.com/LuminariMUD/Duris/issues/555).
- Current branch: [branch/issue-555-stock-qualification](https://github.com/LuminariMUD/Duris/tree/branch/issue-555-stock-qualification).
- Local worktree: `/home/aiwithapex/projects/duris-issue-555`.
- Windows worktree: `\\wsl.localhost\Ubuntu\home\aiwithapex\projects\duris-issue-555`.
- Remote plan: [plan-issue-555.md](https://github.com/LuminariMUD/Duris/blob/branch/issue-555-stock-qualification/docs/ongoing-projects/plan-issue-555.md).
- Planning base: [`f2de272aace60a74e29fbc8abedb945834e9a6a8`](https://github.com/LuminariMUD/Duris/commit/f2de272aace60a74e29fbc8abedb945834e9a6a8), fetched from `origin/master`.

## Implementation handoff

Implementation and local acceptance work are complete. The following open PRs
form the review stack; merge in this order after the required reviews:

1. [#558](https://github.com/LuminariMUD/Duris/pull/558): boot classification,
   branch/issue-555-reboot-shop-stock against master.
2. [#559](https://github.com/LuminariMUD/Duris/pull/559): SQL deficit refill,
   branch/issue-555-refill-shop-stock against #558's branch.
3. [#561](https://github.com/LuminariMUD/Duris/pull/561): atomic flat-file refill,
   branch/issue-555-flatfile-stock against #559's branch.
4. [#562](https://github.com/LuminariMUD/Duris/pull/562): saved SQL identity repair
   and qualification, branch/issue-555-stock-qualification against #561's branch.

Current checkout: /home/aiwithapex/projects/duris-issue-555 on the final branch.
No merge, production operation, migration, or release tag is part of this
handoff. Review and deployment remain owner actions. The sections below retain
the completed design and acceptance reference, rather than unexecuted TODOs.

### Delivered behavior

- economy/shopkeeper_boot.c/.h records a private, atomically synced marker at
  shopkeeper-boot/state relative to the data directory. A proven clean stop
  permits the next ordinary cold boot to refill. Copyover, Redis world recovery,
  and an unclean stop preserve stock. This includes Redis's existing clean
  world-preserving restart mode. Unknown/first-upgrade predecessors also preserve
  stock; a subsequent clean stop establishes eligibility. New shops still receive
  ordinary initial reset stock. Minimal/report/pwipe-recovery runs leave the
  marker alone. Corrupt/unreadable state rejects startup; a failed clean-marker
  write cannot enable refill.
- economy/shopkeeper_restock.c/.h selects only missing finite carried roots from
  the actual initial-reset keeper. Saved copies, including resale goods, count
  toward the target. Equipment and container children do not count as loose
  stock. Existing selected graphs move with their UIDs and children. Saved graphs
  are retained unchanged; produced stock uses its existing path.
- SQL prepares every replacement candidate and deficit before removing a fresh
  keeper, then uses normal object movement and existing snapshot writes/retries.
  Generic restore defaults to preservation; the boot facade grants permission.
  The optional persistence trace includes permission and selected-root count.
- Flat-file refill captures selected graphs, validates shop/custody revisions and
  new UID absence under the existing authority lock, and commits catalog plus
  ownership together before publishing new stock. Bootstrap and refill reuse
  ownership publication. No-deficit boots do not rewrite or advance the catalog.
  Failed commit/publication rejects incomplete startup while retaining recoverable
  durable state.
- Qualification found SQL saved shop item UIDs but omitted them from restoration.
  Valid saved UIDs are now restored; duplicate/invalid UIDs reject publication.
  Legacy snapshots without a UID retain their previous fresh allocation. No
  migration is required.

Ablation: existing Redis markers describe a particular recovery generation and
cannot classify a cold start without a Redis image, so the small local marker
supplies that distinction using existing file primitives. Using actual reset
stock avoids a second reset interpreter, persistent item-origin tracking,
configuration, or a restock service. The authored-area scan found 460 finite
direct G entries across 132 templates, four repeated-type blocks, 92 E entries,
and no P entries inside those shop M blocks. These are configuration counts,
not independently reproduced live defects. The actual graph also covers indirect
loads and container contents.

### Verification

These focused checks pass; previously valid evidence was reused where its owning
code path did not change:

```sh
python3 tests/async/test_shopkeeper_boot.py
python3 tests/async/test_shopkeeper_population.py
python3 tests/async/test_shopkeeper_secondary_binding.py
python3 tests/async/test_dirty_shopkeeper_retry.py
python3 tests/async/test_shopkeeper_save_runtime.py
python3 tests/async/test_shopkeeper_retry_policy.py
python3 tests/async/test_shopkeeper_copyover_compat.py
python3 tests/async/test_spellbook_persistence_contract.py
python3 tests/async/test_flatfile_shopkeeper_restore.py
python3 tests/async/test_flatfile_shopkeeper_repository.py
python3 tests/async/test_flatfile_shopkeeper_bootstrap.py
python3 tests/async/test_flatfile_shopkeeper_ownership.py
python3 tests/async/test_flatfile_shopkeeper_restock.py
```

The production SQL restore/selector harness passes 15 ASan/UBSan scenarios,
including partial/unsold/excess stock, saved container contents, equipment
exclusion, missing snapshots, shared/ambiguous bindings, cleanup, and valid,
duplicate, invalid and legacy UIDs. Boot tests execute separate process/file
transitions. The five flat-file refill ASan/UBSan cases execute the selector,
real catalog/custody transaction and runtime ownership, covering repeat boots,
stale revision, UID collision, storage failure, and post-commit publication
failure/reload. Their world/graph I/O doubles are supplemented by real-server
journeys.

```sh
python3 tests/async/run_shop_reboot_stock_journey.py --backend flatfile --server bin/server/dms_flatfile --report bin/qualification/issue-555-flatfile-journey.json
bash tests/async/with_disposable_mariadb.sh python3 tests/async/run_shop_reboot_stock_journey.py --backend mariadb --server bin/server/dms_new --report bin/qualification/issue-555-mariadb-journey.json
```

Both journeys pass on disposable accounts, authority and private generated world
data. They exercise Maggeynel's authored bag and potion through buy/save/clean
reboot, partial repeated stock, actual resale of a matching stock type and an
unrelated potion, retained unsold/resale UIDs and cost, new container parentage,
another clean reboot without duplication, native copyover, SIGKILL without Redis,
and clean-stop eligibility after crash. Produced goods are actually bought.
Flat-file inspection reconciles catalog and custody. SQL snapshots are
checkpointed through an ordinary paid purchase; free staff purchases do not
checkpoint that keeper. The extra fixture uses road 45016 to avoid existing
merchant and pet-shop procedures.

The game refuses sales of full containers. Preservation of saved container
contents is covered by the production restore harness; the live journey checks
newly replenished container graphs. The shared refill selector preserves all
existing object properties without copying or rewriting saved items.

Qualified binary SHA-256:

- Flat-file: c5bf8285fb54abff16f69bd388698e687f2537e49a5f23588b3213828ca5a455.
- MariaDB: 5f5b9513276047d66b0399a0be894740a67cd8e56aa8ed9632e7a80fbcb5e2c0.

Reports and logs are under bin/qualification/issue-555-*-journey.*. A subsequent
logging-only cleanup overwrites old transcript attempts and retains prior boot
sessions; gameplay actions/assertions are unchanged.

The full-world no-trade control also passes:

```sh
python3 tests/async/run_shop_bootstrap_journey.py --server bin/server/dms_flatfile --areas bin/qualification/issue-555-world/areas --output bin/qualification/issue-555-bootstrap.json
```

Both boots retain the same 1,148,381-byte catalog, SHA-256
7f5991653983a599e44979cd2a30a8ae79e924344bb233dd697edc656cba400b.
The isolated area data was generated with the seven bin/areas/tools/make_*
binaries under bin/qualification/issue-555-world/areas using authored input
symlinks. Checkout-generated areas/world.* files were not modified.

Development MariaDB and client-free flat-file builds pass. The SQL-only UID and
trace repair was rebuilt with make -C src -j4 and used by the successful MariaDB
journey; it is outside the client-free compile path. Logs include
bin/issue-555-final-build.log and bin/issue-555-flatfile-build.log.
Formatting, Clang-Tidy commit hooks, Python compilation, and whitespace checks
pass. Hosted CI completion is not a gate; no full regression campaign was needed.

## Outcome

Restore the shop's valid saved inventory, then refill only the missing limited
stock that a normal reboot should supply. Keep unsold goods and player-sold goods,
including their saved properties and contents.

For a shop whose reboot stock includes one bag:

- Zero bags saved: add one bag during the next normal reboot.
- One bag saved: keep that bag and add none.
- Two bags saved, for example after a player sells one: keep both and add none.

For each finite stock type, add `max(0, reboot target - restored stock count)`.
Never trim saved stock to the target. Subsequent reboots without purchases must
not accumulate more copies. Unlimited production continues through its existing
path. Ordinary area resets, per-shop recovery, copyover, and crash recovery must
not accidentally trigger the normal-reboot refill.

## Evidence and source ownership

The issue reports Maggeynel in room 83385, keeper 83189, internal shop 410, as a
confirmed example. Her finite bag 83185 and potion 3102 are present in the
[area reset block](../../areas/zon/alatorin.zon) and absent from the
[shop's producing list](../../areas/shp/alatorin.shp). The issue's wider inventory
comparison is not a count of independently reproduced defects.

At the planning base:

- [`ne_init_events()`](../../src/world/new_events.c) runs initial zone resets
  before shop restoration. It skips those resets for copyover and active Redis
  world recovery.
- [`boot_db()`](../../src/world/db.c) restores shopkeepers afterward and records
  the boot shopkeepers. `reset_zone()` skips an existing keeper and its dependent
  stock loads. A `G` reset creates one object per successful entry; its numeric
  limit is not a requested quantity. In particular, potion limit 999 does not
  mean the shop should receive 999 potions.
- [`restore_shopkeepers()`](../../src/core/files.c) selects SQL or flat-file
  persistence and rejects incomplete restoration.
- [`sql_restore_shopkeeper_catalog()`](../../src/sql/sql_player.c) stages saved
  inventory, regenerates produced stock, then extracts the matching fresh keeper.
  Its current caller is `sql_restore_shopkeepers()`; the refill must be gated by
  boot context rather than added to generic item materialization.
- [`flatfile_shopkeeper_restore_catalog()`](../../src/flatfile/flatfile_shopkeeper_restore.c)
  also replaces fresh keepers. Its item ownership and shop revisions must remain
  consistent with the catalog. Setting a SQL-style dirty flag is insufficient:
  `save_dirty_shopkeepers()` returns immediately in flat-file mode.
- [`shop.c`](../../src/economy/shop.c) selects sale stock from the keeper's carried
  inventory and identifies unlimited goods through `shop_producing()`.

## Approach

### 1. Establish the normal-reboot stock target

Use the finite inventory actually created by the existing initial zone reset as
the target for that boot, before restoration removes the fresh keeper. This
reuses the existing reset rules, quantities, load decisions, and object creation
checks instead of introducing another interpreter for area files.

Associate the target with the exact shop identity and its known boot-created
keeper. Reuse the existing binding and singleton checks; a shared NPC prototype
alone is not enough. Carry this boot-only information only as far as restoration
needs it, then release it. Do not infer boot provenance from an arbitrary live
keeper found during later recovery.

Before implementation, inventory the finite shop reset forms in the authored
areas, including repeated `G` entries, container `P` children, equipped objects,
and any indirect/random loads. Check them against the actual sale path. This
determines graph handling and fixtures; do not silently reduce the fix to the
two reported objects or only the simplest direct resets.

Use the existing boot/recovery signals to permit refill only when the normal
initial reset ran. Trace clean reboot, copyover, Redis crash recovery, and a crash
without a recoverable world snapshot. The absence of `copyover_boot` alone is
not evidence of an intentional reboot. If the current lifecycle cannot tell a
normal reboot from the last case, resolve that distinction in the owning boot
path before enabling refill; do not classify every cold process start as a
restocking event by default.

### 2. Restore saved goods and add only the deficit

After saved goods are validated and materialized, compare the restored carried
stock with the boot target, excluding unlimited production. Count by object
prototype using the existing shop stock rules. An existing player-sold copy of
the same type counts toward the target; preserve it even if its name, charges,
or other properties differ. No historical origin tracking is needed for this
quantity policy.

Count saleable inventory roots, not equipped items or objects inside another
item. When a missing root is a container, preserve the fresh reset-created
contents as part of its object graph. Do not refill or rewrite the contents of
an already saved container. Keep saved equipment and unrelated resale goods
unchanged.

Prefer transferring only the required fresh object graphs to the staged restored
keeper. Transfer each graph once, retaining its valid identity and resetting its
location links through existing object movement functions. Discard surplus fresh
stock through normal extraction. Verify creation/custody rules before choosing
the exact transfer point; never clone a saved UID or bypass an artifact limit.

Complete validation and preparation before destroying the fresh keeper or
publishing a partially replenished shop. Reuse the current staging cleanup on
failure. A missing snapshot leaves the fresh shop's stock intact and uses the
existing new-shop initialization path. Preserve the existing identity validation
and invalid-snapshot handling; ambiguous identities must not trigger a guessed
merge.

Apply the same quantity rule to both maintained persistence paths:

- SQL: retain catalog staging and the existing transactional replacement/save
  retry path. A failed restore or save must retain the last durable snapshot.
- Flat-file: reuse the existing authority transaction, item custody, and revision
  machinery to commit the replenished catalog and ownership together before
  making new stock tradeable. Leave catalog bytes and revisions unchanged when
  no refill is required. Exercise commit failure and recovery explicitly.

Keep the shared stock decision in one small implementation if both restorers
need it; retain backend-specific durability in its existing owner. Do not add a
general inventory reconciliation framework.

### 3. Prove the behavior through saves and restarts

Extend the existing focused harnesses first. A new focused test is justified only
where the current runners cannot exercise the required boot or persistence path.
Test actual restoration and persistence, not only the arithmetic above.

- Sold-out finite goods return to the boot target after a normal reboot.
- An unsold item retains its UID and properties; another reboot adds nothing.
- Partial stock is topped up correctly when repeated reset entries supply more
  than one copy; quantities above the target are preserved.
- Player-sold goods survive, including modified items, containers with contents,
  and resale goods sharing the reboot item's prototype.
- New containers retain their configured contents; saved containers and equipment
  are unchanged; nested items do not count as separate loose sale stock.
- Unlimited goods remain available; normal area resets and individual recovery
  do not replenish sold-out finite goods.
- Copyover and crash-recovery cases retain pre-recovery stock. Explicitly cover
  the boot-classification decision for a crash without a recoverable world image.
- Shared templates, replicated shops, moved keepers, missing snapshots, and
  invalid/ambiguous bindings retain correct identity and replacement behavior.
- Restore/materialization failure leaves no partial stock or leaked objects.
  Save/commit failure and retry retain durable goods and cannot duplicate refills.
- An isolated gameplay journey buys Maggeynel's bag and potion, saves, normally
  reboots, and buys the replenished goods. Include an unsold copy and a resale
  control, a second reboot, and recovery controls. Cover SQL and flat-file modes
  with disposable data, checking saved item identities as well as shop listings.

## Expected files and validation

Likely runtime owners are `src/world/new_events.c`, `src/world/db.c`,
`src/core/files.c`, `src/sql/sql_player.c`, and
`src/flatfile/flatfile_shopkeeper_restore.c`, plus the existing ownership/catalog
interfaces only where the flat-file atomic update requires them. Confirm the
smallest integration points before editing; these are candidates, not a mandate
to change every file.

Start with and extend these relevant checks:

```sh
python3 tests/async/test_shopkeeper_population.py
python3 tests/async/test_shopkeeper_secondary_binding.py
python3 tests/async/test_dirty_shopkeeper_retry.py
python3 tests/async/test_shopkeeper_copyover_compat.py
python3 tests/async/test_flatfile_shopkeeper_restore.py
python3 tests/async/test_flatfile_shopkeeper_bootstrap.py
python3 tests/async/test_flatfile_shopkeeper_ownership.py
```

Use `tests/async/run_shop_bootstrap_journey.py` for the existing no-trade,
full-world restart control; preserve its byte-identical catalog assertion when
there is no stock deficit. Extend or reuse the existing disposable journey setup
for the buy/save/reboot cases. Run the applicable shop trade tests if those paths
are touched. Record exact commands and results in this plan when implementing.

After C/C++ changes, run `./scripts/format.sh --check`, `make -C src`, and
`git diff --check`. Keep executables and qualification output under `bin/`.
Local executable checks and gameplay/persistence journeys are the acceptance
evidence; hosted CI completion is not a gate. Report any unavailable validation.

## Scope and completion

The planning document and dedicated branch are linked from the issue. Runtime
chunks are published for review as they become ready; dependent changes will
use stacked PRs. Keep this handoff current with their links and exact results.

Implementation is complete only when the acceptance cases above pass and their
results are recorded. A green population test alone does not prove restocking.

No stock is converted to unlimited production, no snapshots are deleted, and no
hard-coded repair for Maggeynel is proposed. The plan adds no new restock service,
settings surface, schema migration, or persistent item-origin tracking without
evidence that the required behavior needs it. Reusing the actual boot stock
removes the need for a second reset parser.

Production restocking, migrations, deployment, and release are separate work and
require the applicable owner authorization. Planning and later isolated local
qualification must preserve unrelated worktrees, credentials, and player data.
