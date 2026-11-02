# Item ownership: findings and the smallest cleanup

Investigated November 2, 2026, against local `master`
`5708e269974ab070ea224f720e7e2e787e2d6671`. Related incident:
[issue #583](https://github.com/LuminariMUD/Duris/issues/583).

Dedicated branch:
[branch/issue-583-memory-authority-plan](https://github.com/LuminariMUD/Duris/tree/branch/issue-583-memory-authority-plan).
Local worktree: `/home/aiwithapex/projects/duris-issue-583-memory-authority-plan`.

**The main problem is a broken authority rule. Ordinary gameplay treats actual
objects in memory as the truth. Several later checks instead treat an optional,
incomplete ownership cache as the truth. Some also let boot-time information
override what happened afterward. Updating every cache on every movement would
make this harder to maintain. The cleanup should remove the inappropriate
decisions from those caches.**

The findings below describe the original baseline. Implementation progress and
remaining work are recorded here; no production deployment or repair is implied.
The initial tracked worktree was clean. Tests use synthetic IDs. Build outputs,
the investigation driver, and result logs remain ignored under `bin/`.

## Implementation handoff

Use the newest branch in the PR stack for continued work. Keep completed chunks
ready for review; do not merge or tag a release as part of this task.

1. **Live artifact owner correction and feeding:** review-ready in
   [PR #589](https://github.com/LuminariMUD/Duris/pull/589), original branch.
   Canonical registration and actual worn/carried/nested placement now
   establish the player holder without an ownership-cache permission check.
   Removed the restored-custody parameter and the attachment-only vector argument
   it required. Tests cover stale/missing cache evidence, rejected duplicate
   bodies, first feed, epic feeding, monolith feeding, timer/soul preservation,
   failed construction, and terminal unload. Source admission is unchanged in
   this chunk: its delayed-read boundary must be resolved before removing that
   separate veto.
2. **Artifact expiry:** review-ready in
   [PR #590](https://github.com/LuminariMUD/Duris/pull/590), stacked on #589.
   Accepted recovery placement erases only boot player locators, keeping
   pinned world projections. The ASan/UBSan artifact admission harness passes,
   including genuine boot tracking repair, construction cancellation, live
   handoff, unload, current-recipient lookup, and actual offline retirement.
3. **Shop revisions:** review-ready in
   [PR #591](https://github.com/LuminariMUD/Duris/pull/591), stacked on #590.
   Shop publication supplies its existing exact revision array to the
   runtime apply function. No serialized result changes. Real adapter/cache tests
   cover an ordinary sale with committed revision 9 despite cached/submitted 1,
   the empty-cache case, buyback at revision 10, and a stocked-container purchase
   with revisions 9 and 3. `test_item_ownership_runtime.py` and
   `test_shop_trade_transaction.py` pass; `make -C src -j4` passed.
   Audit: the only other runtime-apply caller is `item_movement_transaction.c`,
   used for creation grants and adopted-object operator repair. Its generic
   result still contains only a maximum: mixed-revision memory-held repair
   publication needs separate treatment before calling the revision audit done.
4. **NPC containers:** implemented on `branch/issue-583-npc-containers`, stacked
   on #591. Removed both cache vetoes: newly received bags can organize inventory,
   and newly received ordinary items can enter carried bags. Reuses normal `put()`
   permissions, equipment evaluation and trap handling. Real organizer/put/cache
   regression cases pass alongside `test_put_trap_lifecycle.py`,
   `test_get_trap_lifecycle.py`, `test_items_move_in_memory.py`,
   `test_item_movement_input_queue.py`, and `make -C src -j4`.
5. **Remaining:** artifact source admission plus delayed-read/save/unload proof;
   old-holder source cleanup versus damaged-component retention; generic repair
   revision publication; physical floor/copyover capture;
   pet/NORENT compatibility review; specific refusal diagnostics and existing
   inspection; backend and end-to-end acceptance journeys listed below.

Validation for chunk 1: `make -C src -j4` passed (MariaDB development build;
`bin/tests/memory-authority-583/build-live-owner.log`). Focused sanitizer and
checks passed: `python3 tests/async/test_artifact_creation_admission.py`
(ASan/UBSan) and `python3 tests/async/test_player_load_items.py`. Chunk 2 uses the
same sanitizer harness and an incremental `make -C src -j4`.

## The existing design already says what should happen

[ADR 0002](../adr/0002-persistence-reset-memory-is-the-authority.md) says that
items move immediately in memory, the database catches up through one writer,
and loads omit an old holder's stale saved copy. This is an accepted decision,
not a new proposed architecture.

The source largely implements that decision:

- `do_give`, `get`, `drop`, `put`, and ordinary object placement move the actual
  object without asking the ownership cache. `test_items_move_in_memory.py`
  checks those paths.
- `claim_items()` in `src/item/item_claim_repository.c` and
  `flatfile_item_repository_prepare_claim()` make saved ownership agree with
  the captured live holdings. `src/item/item_claim.h` describes the contract.
- `finish_completion()` in `src/player/player_save_pipeline.c:111` acknowledges
  saves without publishing every item's new owner back into the cache.
- `src/player/player_snapshot_capture.c:407` explicitly documents that items
  acquired since login can lack a cache entry even after saving.
- `src/player/player_load_materialize.c:761` explicitly calls the map a database
  cache whose hydration failure must not keep a character out.

Therefore `item_ownership_runtime` is not the live object graph. It is partial
bookkeeping used by remaining durable item operations. A stale or missing entry
is normal under the current design.

## Confirmed failures

### 1. Artifact admission gives that optional cache a veto

`artifact_owned_source_error()` at `src/guild/artifact.c:1027` checks the saved
source and captured durable custody, then compares the separate runtime cache at
line 1062. Owner, root, and parent differences reject the source even when the
cached item revision is older.

The real qualifier, real artifact service, and real ownership map reproduced:

- Correct saved artifact, empty cache: admitted.
- Same saved artifact, older player owner, corpse owner, or container placement
  in the cache: withheld on two consecutive loads.
- Removing just that cache entry: the unchanged saved source is admitted.
- Forgetting the recipient's cache domain does not remove an entry still naming
  a different player or corpse.

The qualification runs before ordinary login's optional cache hydration.
`player_load_items_qualify()` removes the refused item from the admitted graph,
so hydration cannot update it. `artifact_begin_recovery()` calls the same
predicate again. Changing only the first caller would leave the second refusal.

The canonical artifact record already checks the actual registered live object
and pending creation at `artifact.c:1074`. That is a different, useful safeguard
and must survive removal of the stale ownership veto.

### 2. Live artifact owner correction and feeding repeat the mistake

`artifact_reconcile_player_owner()` at `artifact.c:2647` first establishes that
the object is the registered canonical artifact and follows its actual container,
inventory, or equipment pointers to the player. It then lets the ownership cache
reject that conclusion.

The explicit `restored_custody` argument is used only when the cache has no entry.
A stale entry overrides even a correct restored record. Attachment calls this
function before normal session cache hydration (`player_load_items.c:404`).

The executable probe placed the canonical artifact on player 77, supplied correct
restored custody, and seeded an old cache entry naming player 88. Owner correction
failed and feeding was rejected. Removing only the cache entry allowed correction
and feeding with the same live object. Existing code also invokes this correction
from epic feeding in `artifact_guild_state.c:188`.

**Smallest cleanup:** once canonical identity and actual live placement establish
the holder, update location tracking from that holder. Keep soul binding, timer
rules, and canonical identity checks. Drop the redundant ownership-cache
permission check and the restored-custody plumbing it alone needs.

### 3. Expected old saved copies are converted into whole-bag retention

The repository correctly omits a source whose durable owner is somebody else
(`player_load_repository.c:895`). Its comment at line 568 says the former holder's
next save should remove that stale copy.

`player_load_items_qualify()` then revisits those omitted raw sources at
`player_load_items.c:997`, treats a foreign artifact as a retention reason, and
spreads retention through both raw and reconstructed container links at line 1110.

Two independent synthetic cases retained all three rows of a bag containing an
artifact and an ordinary sibling:

1. The artifact's cache entry named an old owner.
2. The repository had already omitted a foreign-owned artifact, but its old raw
   source row remained for inspection.

The second case needs no runtime-cache conflict at all. It reverses the normal
stale-copy cleanup rule and can withhold unrelated possessions.

**Smallest cleanup:** preserve the repository's normal distinction between
confirmed foreign-owned leftovers and unreadable/contradictory source data.
Do not promote the former to a whole-component hold merely because it is an
artifact. Preserve genuine damaged components until a trustworthy recovery can
be made. Cases where no valid current payload can be established still need
retention; this is not a blanket instruction to delete every foreign row.

### 4. Artifact expiry can follow the owner from boot after a later handoff

`event_artifact_check_poof_sql()` at `artifact.c:3741` prefers player locators in
`canonical_payloads` over the current location. Its comment says placement clears
those boot sources.

That is false for successful recovery: `artifact_object_placed()` returns at
line 1242 before the clear at line 1249. `artifact_row_store()` at line 507 updates
the current location but also leaves the old sources intact.

The probe supplied a boot source naming player 77, recovered the artifact, placed
it on player 88, and called the real updater, which correctly recorded 88.
After unloading the object, the real expiry event nevertheless selected player
77. The source list still named 77.

**Smallest cleanup:** retire the obsolete boot-time player locator once accepted
live placement establishes the holder. Keep source projections still needed for
source-qualified world recovery; mutable player admission does not need an old
boot locator to overrule current location. Add a handoff/unload/expiry test,
including a genuine boot-time tracking repair, so correcting one does not break
the other.

### 5. World recovery also lets old cache ownership overrule a live floor item

`capture_item_tree()` at `src/world/world_recovery_pipeline.c:297` captures the
actual object tree. At line 315 it consults cached ownership. A stale player owner
has a specific exception; an old corpse, pet, locker, or different room does not.

With the same physical object in room 2300, the real capture function:

- included it with no cache entry;
- included it with an old player entry;
- marked the tree to be skipped with an old corpse, pet, locker, or room entry.

The copyover branch instead exported the old room 9999 ownership for that object
physically in room 2300. This proves stale custody is handed forward; it does not
prove every such copyover loses the object, because restore has more checks.

**Smallest cleanup:** capture actual live floor placement and classify the actual
object's domain, including logical corpse roots. Leave persisted-duplicate
exclusion at restore, where saved holdings are available. Expanding a list of
special exceptions for each former owner would repeat the original design error.
This finding concerns world recovery/copyover; it is not proof of loss from an
independent ordinary room, corpse, or player save.

### 6. Shop publication discards exact revisions and writes incorrect ones

`publish_ownership()` in `src/economy/shop_trade_transaction.c:71` receives a
per-item result, reduces the exact revisions to one maximum at line 143, then
calls `item_ownership_runtime_apply()`.

At `src/item/item_ownership_runtime.c:570`, that function either increments the
old cached revision or assigns the maximum to each item. The probe used the real
shop adapter and real cache implementation with exact committed revisions
`9, 3`:

- With cached/submitted revisions `1, 1`, it published `2, 2`.
- With no cached entries, it published `9, 9`.

Both results are wrong. MariaDB's transfer implementation increments each item's
own revision (`item_transfer_repository.c:1272`); the flat-file implementation
does the same (`flatfile_item_repository.c:844`). The maximum is a summary, not
the exact version of every item. A cache comparison can therefore report an item
as newer than it really is, or miss a real advance.

The two-item input is an API-boundary probe, not a player selling a full bag:
`shop.c:1272` prohibits that gameplay action. A separate ordinary single-item sale
probe supplies committed revision `9` and observes cached revision `2`; this
understatement does not require a container or batch. Shop stock uses exact
revision checks on subsequent trades, so this matters outside artifact loading.

**Smallest cleanup:** publish the exact per-item results already present in shop
completions. Do not invent another revision scheme. The general transfer result
contains only a maximum; consumers of that result must not treat an estimate as
an exact item version. Audit its actual remaining callers before changing the
serialized result format.

This is a separate economy defect, not a claim that selling an artifact caused
#583. Ordinary shop sale, auction listing, and collector enrollment reject
artifacts (`shop.c:1255`, `auction_houses.c:468`, `collector_policy.c:53`). Those
unreachable artifact trades must not justify more artifact admission machinery.

## Other decisions that cannot be hidden inside a cache cleanup

- **Delayed load replies:** loading uses a separate reader thread, not the one
  writer (`player_load_pipeline.c:56,190`). The hold checks the requested player's
  pending work before starting the read. The game publishes critical completions
  before load results (`comm.c:2389`). In the probe, an earlier source was rejected
  while a different canonical live holder existed, then became admissible after
  that holder unloaded. This is a boundary reproduction, not a full threaded
  duplicate-item journey. A cleanup must test another holder's handoff/save/unload
  while a read is outstanding. A stale cache is not a demonstrated solution to
  this race. Reuse the existing pending-save/load mechanisms and canonical
  reservation when an actual in-flight operation requires waiting or a fresh read.
- **Pet teardown:** `hold_durable_pet_items()` (`handler.c:3696`) removes certain
  objects from play according to the cache, and is reached on charm break, death,
  and extraction. Existing tests deliberately preserve stored raised-pet custody.
  Do not delete this behavior merely because the map is being reduced. First
  establish the intended raised-pet return/death journey and preserve it using
  actual live/pending state.
- **NORENT:** `player_snapshot_capture.c:367` uses cache presence to preserve
  some NORENT items. This is an explicit durable-item compatibility exception,
  with a separate key-rent rule. Removing the map must not silently erase
  saved equipment or change which keys survive rent.
- **NPC bag handling:** `CheckEqWorthUsing()` (`mobact.c:7102`) refuses normal
  container organization merely because the bag has a cache entry. The comment
  requires a second transaction, although scavengers now use ordinary memory
  movement (`mobact.c:8168`). This is a source-confirmed leftover gameplay veto;
  remove it with a focused scavenger/container journey.

These consumers explain why deleting the entire cache file in one operation is
not yet a complete patch. They do not justify keeping its general authority over
live gameplay.

## How this accumulated, and why tests stayed green

Git history establishes the order:

- `a573027603`, September 28: memory-first item movement and economy claims.
- `53d0da2f76`, October 17: artifact identity integration introduced the cache
  admission veto and foreign-source retention path.
- `2c70abf172`, October 18: owner recovery introduced the additional cache check
  after following the actual live owner.

The existing admission fixture covers matching entries, equal-revision conflicts,
and newer entries, but misses an older entry after a normal handoff.
More seriously, `test_artifact_creation_admission.py:545` deliberately asserts
that a canonical live wearer's ownership correction and feeding fail when the
cache disagrees or is missing. Tests are enforcing that incorrect authority rule.

The world recovery suite and memory-movement contracts also pass while the new
probes reproduce the failures above. Passing individual subsystems is not proof
of the full receive/save/unload/login journey.

## Recommended implementation order

1. **Restore the artifact authority rule in the existing code.** Remove the
   general ownership-cache veto from qualified source admission and the redundant
   cache check from live owner correction. Keep canonical UID, live-body/pending
   reservation, retirement, source-owner, and valid-container checks. Prove delayed
   reply handling before considering the admission change complete. Use the same
   shared rule for qualification and construction.
2. **Remove the ways obsolete evidence becomes permanent.** Stop turning proven
   old-holder leftovers into retained bags. Retire obsolete boot player locators
   after successful live placement. Keep failed-construction rollback and genuine
   damaged-source preservation. Recovery should use the existing fresh login/load
   path; a force-load command or new retention service is unnecessary.
3. **Correct the other concrete cache consumers separately.** Publish exact shop
   results; make floor capture follow the physical tree; remove the obsolete NPC
   container veto. Preserve pet and NORENT behavior through their explicit
   gameplay rules. Reduce or remove cache fields/APIs only after their actual
   remaining consumers no longer need them.
4. **Make the remaining refusals understandable.** Log the actual failed condition
   at the existing boundary and show it through existing inspection. The current
   `ESTALE` bucket combines identity, source, topology, and cache conflicts, while
   `artifact hunt` prints saved custody but omits the conflicting runtime entry
   (`artifact.c:4013`). This needs a useful error reason, not a diagnostics platform.

The desired end state is small: live objects decide current location; saved
payloads restore unloaded objects; one saved owner filters old copies; the
artifact record prevents a second unique artifact and preserves timer/soul
state. Real pending economy transactions retain the state they need to settle.

Do not add a new ownership manager, per-movement database operation, cache-sync
worker, reconciliation service, journal, migration, or universal force-recovery
command. An older-revision exception could contain #583, but it leaves the live
feeding, stale boot locator, retention, and inaccurate-revision problems intact.

## Evidence and completion criteria

The executable investigation extends the existing artifact admission harness,
including real construction, extraction, canonical registration, topology, and
qualification. Shop publication and world capture functions are extracted
verbatim from the current source. The harness uses existing stubs for unrelated
server integration and has no game connection.

Local evidence:

```sh
python3 bin/tests/investigate_memory_authority_583.py
cat bin/tests/memory-authority-583/result.log
```

It compiles with ASan/UBSan and `-fno-sanitize-recover=all`. All new assertions
and all original scenarios in that admission harness passed. The new assertions
demonstrate current failures; they are not tests of a repaired implementation.

Additional checks completed:

- `python3 tests/async/test_items_move_in_memory.py` — passed; source contracts.
- `python3 tests/async/test_player_load_items.py` — passed; executable item loader.
- `python3 tests/async/test_world_recovery_pipeline.py` — passed; existing recovery
  capture/restore and rollback cases.
- `TMPDIR="$PWD/bin/tests" python3 tests/async/test_flatfile_item_repository.py`
  — passed; existing flat-file ownership repository cases.
- `bash tests/async/run_item_transfer_schema_mysql.sh` — passed using its own
  disposable MariaDB server and synthetic schema; claims, replay, transfer,
  destruction, ledger, and outbox cases. Output is in
  `bin/tests/memory-authority-583/mysql-transfer.log`.
- `TMPDIR="$PWD/bin/tests" bash tests/async/run_player_save_claim_mysql.sh` — passed
  using a separate disposable MariaDB server; save claims, load filtering,
  retained evidence, rollback, rent, and related persistence cases. Output is in
  `bin/tests/memory-authority-583/mysql-save-load.log`.

Before any cleanup is called finished, extend existing regression suites with
ordinary handoff, corpse loot, nested movement, repeated login, and feeding
journeys; both admission and post-attachment behavior must succeed. Include the
former owner's stale save, handoff during an outstanding read, current-owner
offline expiry, floor/copyover after corpse or locker pickup, and an ordinary
shop sale/buyback after handoffs changed the saved revision. Exercise mixed-revision
results at actual supported multi-item boundaries. Preserve UID,
affects/enhancements, timer, soul, mana, nesting, and unrelated inventory on both
MariaDB and flat-file paths. Existing duplicate,
retired-identity, corrupted-source, and rollback controls must continue to pass.

No full serving-MUD handoff/relogin or restart journey was performed in this
investigation, and no production incident was independently re-inspected. The
specific historical cache fields in #583 remain unavailable. No production
repair, deployment, migration, or implementation claim is made by this report.
