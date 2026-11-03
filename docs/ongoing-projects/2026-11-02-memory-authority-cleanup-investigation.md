# Memory authority cleanup: review and integration

[Issue #583](https://github.com/LuminariMUD/Duris/issues/583).
Delivery branch: `master`. Historical implementation worktree:
`/home/aiwithapex/projects/duris-issue-583-memory-authority-plan`.
The final integration record is in [PR #607](https://github.com/LuminariMUD/Duris/pull/607).

**Status:** review and local acceptance are complete. Runtime fixes are merged
into `master`; this final PR records sequential integration of #593–#597 and
#603–#607. Required companions were included before their introducing PRs merged.
Both builds and all focused native/backend and serving checks pass; all started
checks have completed. No release, deployment or production repair is included.

## Outcome and limits

Follow [ADR 0002](../adr/0002-persistence-reset-memory-is-the-authority.md):
live objects establish current placement; saved payloads restore unloaded objects;
durable ownership filters former holders' copies. The optional ownership cache
must not veto ordinary movement, valid artifact recovery or feeding.

Keep canonical uniqueness, pending operations, retirement, source qualification,
damaged-source retention, timer/soul rules and required economy settlement.
Keep the explicit pet-custody and durable NORENT/key-rent compatibility rules.
These real consumers still need cache bookkeeping; deleting the entire cache
would break them.

No new ownership manager, cache-sync worker, per-movement persistence, retry
service, journal, migration, revision format or force-recovery command is needed.
Do not expand this into a general cache-removal or hardening project.

## Necessary changes already implemented

These are the acceptance contract and the owning files, not another work queue.

- **Artifact admission and feeding** — `src/guild/artifact.c` and
  `src/player/player_load_items.c`: the qualifier and constructor share source,
  captured-custody and canonical checks. Live owner correction follows the actual
  canonical body's carried/worn/nested placement. Cache disagreement alone,
  including an apparently newer revision, grants no authority over that body.
  Competing bodies, pending creation, retired identities and invalid sources
  remain rejected.
- **Delayed reads** — `src/player/player_load_pipeline.c`,
  `player_save_worker.h`, `player_load_items.c`, `player_load_materialize.c`,
  `player_load_offline.c` and `src/account/account.c`: artifact loads use the
  existing writer counters to detect overlapping work. Refresh through the
  existing load queue with the original identity, callback and deadline.
  Never retain a source merely because its read is stale. Direct/boot reads
  retain their quiescent contract. Unrelated writes can also invalidate a read;
  this conservative behavior does not justify a new per-item tracking scheme.
- **Old copies and expiry** — the artifact service and item qualifier omit only
  proven obsolete/retired copies, preserving independent bag contents and
  damaged or unresolved evidence. Successful live recovery discards obsolete
  boot player and pet locators, preserving pinned world sources and cancellation
  rollback. Offline expiry then follows the current holder.
- **Floor/copyover capture** — `src/world/world_recovery_pipeline.c` captures
  the physical tree. Copyover includes cached metadata only when it matches the
  actual room or logical corpse root. Saved-duplicate exclusion stays at restore;
  legacy marked records keep their required compatibility path.
  Restore accepts active room custody matching the captured room, vnum and
  topology on both backends; conflicting or inactive custody still excludes it.
  An item encountered twice across capture pulses invalidates the generation
  instead of silently omitting the second tree and its unrelated contents.
  The previous published generation remains available; a later capture retries.
- **Shop revisions** — `src/economy/shop_trade_transaction.c` passes its
  existing per-item committed revisions to `src/item/item_ownership_runtime.c`.
  The other caller, creation/adopted-object repair in
  `src/item/item_movement_transaction.c`, uses exact revisions where available;
  unknown memory-held batch revisions are zero, never a guessed maximum.
  Custody remains available to pet/rent consumers. Artifact sales and full-bag
  sales are prohibited gameplay and do not justify extra machinery.
  Creation batches accept unknown cached parent revisions; the existing writer
  claim resolves the actual revision on both backends.
- **NPC containers** — `src/mob/mobact.c` uses ordinary equipment and `put()`
  rules after loot movement, preserving capacity, artifact restrictions and traps.
  `src/world/handler.c` pet teardown and `src/player/player_snapshot_capture.c`
  rent behavior remain compatible with unknown cached revisions.
- **Diagnostics and recovery** — existing artifact logs name the failed condition
  and distinguish source, captured custody and optional cache values.
  `artifact hunt <initial>` remains read-only; staff notices remain bounded.
  Inspect, correct genuine source damage through its authorized workflow, then
  load afresh through the same qualifier. Resolve actual live/pending reservations
  before retrying; no bypass or unconditional release.

## Review handoff

The aggregate diff from `5708e269974ab070ea224f720e7e2e787e2d6671` was reviewed
against this contract and the assertions/results below. No implementation task
remains open. The matching-room recovery companion from #607 was brought into
#593 before its merge; the repaired-container companion from #606 was brought
into #597. Current master already supplied #603's whole-load pet guard and
original-deadline refresh; those controls were preserved while integrating #594.
The later companion PRs retain their review history and acceptance documentation.

For requested review changes, reuse the existing paths/tests and repeat only
affected checks. C/C++ edits require formatting and `make -C src`; shared
persistence changes also require the flat-file build. Keep fixes committed,
pushed and review-ready, with this document current. No blanket burn-in or CI wait.

## November 3 integration verification

The open PRs in the requested range were #593–#597 and #603–#607. #599 was
already merged; #598 and #600–#602 are issues. Each delivery preserves ancestry,
integrates current master without force pushes, and receives its own review and
merge. Existing worktrees and unrelated source fixes are preserved.

Review found an additional loss case in multi-pulse floor capture: a child moved
from a captured bag into an unvisited bag caused the entire second tree to be
silently omitted. The new regression fails with the original skip behavior and
passes after capture rejects the inconsistent generation. A fresh capture then
restores both bags and both children. Matching-room recovery was included in the
same PR, with no unsafe intermediate merge.

Focused executable checks passed for world capture/restore, artifact admission
and diagnostics, player loading/refresh, exact/unknown transfer revisions,
creation batches, shop publication, rent and pet teardown. Both maintained server
builds, formatting, diff checks and the pre-commit clang-tidy checks passed.
The current-master offline-load source assertion and overlapping test stubs were
reconciled. Diagnostics tests distinguish whole-load refresh from a source-level
construction refusal. The feeding journey bounds retries for an explicit random
opening-attack fumble while retaining the exactly-once award assertion.

Disposable serving checks passed for MariaDB/Redis outage, crash recovery and
matching-room floor UID pickup/save; both artifact backends' ordinary handoffs,
save/unload, repeated same-uptime login, stale tracking, feeding and restart; and
both shop backends' exact-revision sale/buyback, batch purchases and restart with
all 108 ration UIDs, nesting and wallet intact. MariaDB artifact conflict cleanup
and current-holder offline expiry retain their separate serving coverage.

This run's ignored evidence is in
`/tmp/duris-review-pr593-607/bin/review-pr593-607/`: `overlap-before-fix.log`,
`world-after-fix.log`, `world-journey.log`, `594-admission.log`,
`595-admission.log`, `596-admission.log`, `596-serving-{mariadb,flatfile}.log`,
`597-{flat-items,mysql-transfer}.log`, `603-admission.log`,
`603-serving-{mariadb,flatfile}.log`, `604-shop-{mariadb,flatfile}.{log,json}`,
`605-{admission,items}.log` and the corresponding build logs.
The original acceptance evidence below remains historical; its proof limits
still apply. No release, deployment or production mutation is part of this work.

## Required proof and existing evidence

Acceptance requires ordinary handoff, corpse loot, nested movement,
save/unload/repeated login and feeding to work through admission and attachment.
Also cover the former holder's stale save, handoff/save/unload during an outstanding
read, current-holder offline expiry, floor/copyover after corpse or locker pickup,
and shop sale/buyback after handoffs advance revisions. Exercise mixed revisions
at a supported multi-item boundary. Preserve UID, affects/enhancements, timer,
soul, mana, nesting and unrelated inventory on both MariaDB and flat-file paths.
Duplicate, retirement, corruption, rollback, pet lifetime/teardown and rent/key
controls must continue to hold.

Existing results are recorded below; a green test counts only for its assertions.
Do not rerun the original investigation driver: it asserts the old failures.

- **Serving, both backends:** artifact handoff, repeated login, stale tracking,
  feeding and cold restart; shop handoff/sale/buyback with exact revision advances,
  then restart preserving 108 ration UIDs, nesting and wallet. MariaDB additionally
  exercised legacy conflict cleanup, offline expiry and a fresh artifact generation.
- **Native regression suites:** `test_artifact_creation_admission.py` covers real
  canonical construction, corpse binding, nested recovery, ordinary/epic/monolith
  feeding, old-holder cleanup, expiry and delayed replies. Its threaded read uses
  a stubbed writer/storage boundary. `test_player_load_{items,pipeline,offline}.py`
  covers loading/refresh; `test_artifact_hunt_inspection.py` covers read-only
  diagnostics. Sanitizer checks passed where enabled.
- **Other native suites:** `test_world_recovery_pipeline.py` covers actual
  capture/restore codecs, stale corpse/locker/pet/room metadata, logical corpse
  roots, duplicates and rollback. `test_item_ownership_runtime.py` and
  `test_shop_trade_transaction.py` cover exact/mixed revisions.
  `test_put_trap_lifecycle.py`, `test_get_trap_lifecycle.py`,
  `test_items_move_in_memory.py` and `test_item_movement_input_queue.py` cover
  NPC/movement/trap controls.
- **Compatibility/payloads:** `test_player_snapshot_capture.py` and
  `test_pet_control_drop.py` cover unknown-revision rent/pet behavior;
  `test_pet_restart_journey.py` passed two flat-file restart cycles and finite/
  permanent-pet equipment/lifetime checks. `test_artifact_mana_game.py` covers
  mana conservation/reload. `run_player_load_repository_mysql.sh`,
  `run_player_save_claim_mysql.sh`, `test_flatfile_player_repository.py` and
  `test_flatfile_item_repository.py` cover payloads, claims, retention and rollback.
- **Final review follow-ups:** raw-source diagnostic regressions failed before
  #605 and pass afterward. `test_item_transfer_creation_batch.py`, the real public
  batch adapter, flat-file nested creation and the disposable MariaDB transfer
  suite pass with an unknown parent revision (including fifty SQL-created roots).
  Flat-file room recovery distinguishes matching custody from wrong room, vnum,
  root and parent. `run_world_recovery_journey.py` passes real MariaDB/Redis
  outage/recovery/crash and matching-room floor UID pickup/save. Formatting and
  both server builds pass.

All test paths above are under `tests/async/`; run Python files with `python3`
and shell files with `bash`. Local evidence is under ignored
`bin/tests/memory-authority-583/`: `final-admission.log`,
`serving-{mariadb,flatfile}.log`, `shop-{mariadb,flatfile}-run.log`,
`shop-{mariadb,flatfile}.json`, `pet-restart.log`,
`{norent,pet}-unknown.log` and `final-{mysql-payloads,flat-payloads,mysql-save-load,flat-items,mana}.log`.
Artifact reports are `bin/analysis/artifact-owner/{mariadb,flatfile}.json`.
Final review logs in the same test directory are `review-retained-source.log`,
`review-load-items.log`, `review-container-{codec,input,flat,mysql,transfer-codec}.log`,
`review-room-{pipeline,flat,serving}.log` and the corresponding `review-*-build-*.log`.
Earlier chunk checks and builds are recorded in the PRs. Missing local evidence
in a new checkout is not proof of failure or permission to claim a pass.

Exact build and serving commands, only when relevant work requires repeating them:

```sh
make -C src -j4
make -C src PERSISTENCE_BACKEND=flatfile BIN_ROOT="$PWD/bin/memory-authority-flat" -j4
bash tests/async/with_disposable_mariadb.sh python3 tests/async/test_artifact_owner_restart_journey.py --backend mariadb --server bin/server/dms_new
python3 tests/async/test_artifact_owner_restart_journey.py --backend flatfile --server bin/memory-authority-flat/server/dms_new
bash tests/async/with_disposable_mariadb.sh python3 tests/async/test_shop_multi_buy_journey.py --backend mariadb --server bin/server/dms_new --report bin/tests/memory-authority-583/shop-mariadb.json
python3 tests/async/test_shop_multi_buy_journey.py --backend flatfile --server bin/memory-authority-flat/server/dms_new --report bin/tests/memory-authority-583/shop-flatfile.json
TMPDIR="$PWD/bin/tests" python3 tests/async/test_pet_restart_journey.py "$PWD/bin/memory-authority-flat/server/dms_new"
bash tests/async/with_disposable_mariadb.sh python3 tests/async/run_world_recovery_journey.py bin/server/dms_new
```

Use disposable schemas/state and private loopback servers. Redis crash recovery
has the serving proof above; file copyover has native codec/restore coverage.
The threaded delayed-read harness uses a stubbed writer/storage boundary,
supported by separate serving save/login journeys on both backends. A deliberately
delayed real-database journey and serving file copyover remain unverified.
The production incident and historical cache fields were not re-inspected.

## Review stack

In dependency order, with details and history retained in Git/PRs:
[#589](https://github.com/LuminariMUD/Duris/pull/589) →
[#590](https://github.com/LuminariMUD/Duris/pull/590) →
[#591](https://github.com/LuminariMUD/Duris/pull/591) →
[#592](https://github.com/LuminariMUD/Duris/pull/592) →
[#593](https://github.com/LuminariMUD/Duris/pull/593) →
[#594](https://github.com/LuminariMUD/Duris/pull/594) →
[#595](https://github.com/LuminariMUD/Duris/pull/595) →
[#596](https://github.com/LuminariMUD/Duris/pull/596) →
[#597](https://github.com/LuminariMUD/Duris/pull/597) →
[#603](https://github.com/LuminariMUD/Duris/pull/603) →
[#604](https://github.com/LuminariMUD/Duris/pull/604) →
[#605](https://github.com/LuminariMUD/Duris/pull/605) →
[#606](https://github.com/LuminariMUD/Duris/pull/606) →
[#607](https://github.com/LuminariMUD/Duris/pull/607).
