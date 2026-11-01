# Issue #555: refill missing shop stock after a normal reboot

Status: planned; implementation has not started. Updated 2026-11-01.

- Issue: [#555 — reboot-only shop stock is discarded](https://github.com/LuminariMUD/Duris/issues/555).
- Branch: [`branch/issue-555-reboot-shop-stock`](https://github.com/LuminariMUD/Duris/tree/branch/issue-555-reboot-shop-stock).
- Local worktree: `/home/aiwithapex/projects/duris-issue-555`.
- Windows worktree: `\\wsl.localhost\Ubuntu\home\aiwithapex\projects\duris-issue-555`.
- Remote plan: [plan-issue-555.md](https://github.com/LuminariMUD/Duris/blob/branch/issue-555-reboot-shop-stock/docs/ongoing-projects/plan-issue-555.md).
- Planning base: [`f2de272aace60a74e29fbc8abedb945834e9a6a8`](https://github.com/LuminariMUD/Duris/commit/f2de272aace60a74e29fbc8abedb945834e9a6a8), fetched from `origin/master`.

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

This branch currently contains planning documentation only. Its delivery is a
reviewed plan committed and pushed on the dedicated branch, with this issue link
and an issue comment linking back to the branch, plan, and local worktree.

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
