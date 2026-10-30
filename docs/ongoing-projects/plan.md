# Issue #419: dispose of NORENT keys at intentional rent

Status: **implemented; local qualification complete; original live-instance attribution unavailable**.
Updated 2026-10-30.
Issue: [Duris #419](https://github.com/LuminariMUD/Duris/issues/419).
Branch: [branch/issue-419-plan](https://github.com/LuminariMUD/Duris/tree/branch/issue-419-plan).
Source baseline: `master` at `b23ea8c65a467d17683ccd5de91f66b362209d06`.
Worktree: `/home/aiwithapex/projects/duris-worktrees/issue-419-plan`.

The implementation and measured qualification results are recorded below.
Production deployment and attribution to the reporter's specific item are not
claimed. The previous #428 plan and its qualification history are preserved byte-for-byte in
[plan-issue-428.md](plan-issue-428.md).

The newer master #437 plan is also preserved byte-for-byte in
[plan-issue-437.md](plan-issue-437.md) during PR integration.

## Outcome

After a successful intentional rent save, a genuine temporary key carried,
equipped or nested on the player must be absent when that player reconnects.
This includes Golden Hall key 40401 and both freshly created and previously
owned copies. Its durable custody must record the disposal so an older snapshot
cannot restore it. MariaDB and flatfile-primary must agree.

Preserve unrelated durable assets, retained/unmaterialized item components,
ordinary save behavior and existing crash/copyover recovery semantics. Establish
separately whether this conditional defect caused the reported live observation;
a synthetic reproduction is not proof about that particular item.

## Evidence from the current codebase

The issue was read, including its empty comment thread, but its older revision
and reproduction were not used as proof of current behavior.

- `areas/obj/gold_hal.obj:16` defines key 40401 with type 18 and flags 8388608.
  `src/core/defines.h:127,218` identifies these as `ITEM_KEY` and
  `ITEM_NORENT`. The key's eight values are zero. The zone equips it on paladin
  40400 in room 40401 (`areas/zon/gold_hal.zon:654-655`); the east gate in
  `areas/wld/gold_hal.wld:18-31` requires 40401.
- `src/item/objconv.c:220-226` sets NORENT for keys, and
  `src/world/db.c:3252` calls that conversion during creation. An area edit or
  special case for vnum 40401 would address neither the shared cause nor custody.
  Generated production area data has not been inspected in this planning task.
- Both `inn()` and `undead_inn()` in `src/specs/specs.room.c` submit
  `RENT_INN`. `do_quit()` and the trusted early exit in `do_camp()` in
  `src/cmd/actoth.c` also use that intent. The normal camp completion uses
  `RENT_CAMPED`, and idle departure uses `RENT_LINKDEAD`.
- `persistence_save_character_terminal()` at `src/cmd/actoth.c:2133` captures
  and queues a full checkpoint, invokes the locker hook, and returns without
  waiting for durable completion. Its callers extract the character.
  Queue failure is reported but does not keep the character in the game.
  This established asynchronous logout behavior is a constraint on this repair.
- `src/player/player_snapshot_capture.c:356-369` skips NORENT objects only
  when their runtime ownership is not active. The player capture calls that
  traversal with `omit_norent=true` for every intent, even though
  `player_snapshot.save_intent` already exists. The skip occurs before child
  traversal. Private recursion, public list/tree capture, player capture and
  pet capture share machinery, so the repair must not change every caller.
- A new executable probe linked the production capture, codec and runtime
  ownership modules with the existing engine stubs. All **36 baseline cases**
  passed: six intents (INN, CRASH, CRASH2, QUIT, LINKDEAD, CAMPED), two ownership
  states, and carried/held/nested placement. For every intent, the fresh key
  disappeared from the encoded/decoded item list and the active key survived
  with its UID, NORENT flag and topology. A nested bag remained in either case.
  This independently confirms the reported boundary and also demonstrates
  that fresh keys are currently omitted from crash checkpoints.
- `src/player/player_snapshot_repository.c::apply_items()` claims the captured
  graph, replaces player payload rows, and commits inside the player-save SQL
  transaction. `src/flatfile/flatfile_player_repository.c` prepares one ownership
  catalog image and commits it with the player image through the existing
  authority transaction.
- `src/item/item_claim.c`, `item_claim_repository.c`, and
  `src/flatfile/flatfile_item_repository.c` already prevent a destroyed UID
  from being reclaimed by a stale save. Ordinary snapshot omission does not
  create that destruction record.
- `src/world/handler.c:3205-3216` explicitly explains why `extract_obj()`
  does not retire custody: extraction is also used during shutdown, copyover
  and bulk teardown. Unheld active player ownership rows can be reaped at boot;
  that is not immediate, replay-resistant rent disposal.
- `tests/async/test_player_save_claim.py` protects the general active-custody
  NORENT safeguard. `test_player_snapshot_capture.py` has a usable production
  capture/codec harness. The flat-file and MariaDB claim harnesses already
  exercise destroyed-item exclusion; existing socket journeys supply disposable
  worlds, accounts, backend setup, restart and copyover helpers.

No open PR mentioning 419 was returned by the GitHub PR search. Targeted
searches for “Golden” and “rent” found no open matching issue in the
`max757/duris` GitLab mirror. #419 is the work item for this branch; this is not
a claim that every mirror record has been audited.

## Policy and non-goals

1. **Disposal trigger:** `RENT_INN` plus a materialized player's item whose
   actual type is `ITEM_KEY` and whose actual flags include `ITEM_NORENT`.
   Apply this consistently to every existing RENT_INN producer, including
   explicit quit and the trusted camp shortcut. Do not reinterpret the numeric
   intent names: RENT_QUIT is also used for ordinary saves.
2. **Eligibility:** use type and flag, not vnum, name, break chance, or whether
   a runtime ownership entry happened to hydrate. All genuine NORENT keys get
   the rule; a NORENT non-key retains the current durable-asset safeguard.
   A key without the flag is a preservation control, even though normal key
   creation adds it.
3. **Recovery compatibility:** do not dispose on RENT_CRASH, RENT_CRASH2 or
   copyover, nor add disposal to CAMPED, LINKDEAD, death, pets, lockers, corpses
   or world-item saves. Preserve their existing behavior. In particular,
   current ordinary player checkpoints omit fresh NORENT keys and retain
   active ones; this plan does not silently turn fresh-key crash recovery into
   a new feature. Test copyover separately because it also serializes live
   objects. Record any difference between checkpoint recovery and actual
   copyover instead of claiming one proves the other.
4. **Atomicity:** committed disposal and the saved inventory must agree.
   A replay of a pre-rent snapshot cannot revive a retired UID; repeating the
   same rent save must be safe. Before commit, failures must not leave a
   half-updated ownership/payload pair. Existing queue failure and terminal
   writer failure reporting remain in place; this issue does not promise a
   successful logout is durable when the current save queue itself fails.
5. **Preservation:** a key inside a saved bag is removed without removing the
   bag or unrelated contents. Protected retained source rows are not decoded
   or reclassified as ordinary live items. Do not expand the policy to missing,
   malformed or unmaterialized assets based on guessed type/flags.

No area flag change, new setting, new service, global extraction hook, per-key
writer job, production inventory migration, key-break/relocking redesign
(#418), or general persistence rewrite is needed. Do not change the timing of
logout, bypass the writer, or run production mutations as part of this work.

## Ablated implementation sequence

### 1. Add the failing behavioral regressions

Extend the existing production capture/codec harness and both save-claim
harnesses. The decisive failure is a successfully applied RENT_INN save whose
active key can still load; capture inclusion alone is not the final assertion,
because the worker needs the candidate's UID to retire it.

Use fresh and active key 40401 in carried, HOLD and nested placements. Include
multiple keys, a durable bag with ordinary siblings, an active NORENT non-key,
an unflagged key, and an already destroyed key. Also cover a key under a
normally omitted NORENT container: today's early return must not hide a
candidate from the disposal operation. Establish the existing behavior of
non-rent intents before modifying it.

### 2. Carry rent candidates to the existing save transaction

Keep capture non-mutating. For the main player's RENT_INN item graph, include
candidate key rows even when they have no runtime ownership entry. Existing
`save_intent`, UID, type, flags and item topology contain the required data:
reuse them instead of adding a second disposal queue or a wire-format version.

Preserve ordinary parent indices for saved containers. For an ancestor that
the existing filter omits, traverse its skipped subtree only to collect
eligible keys as disposal-only root rows in this RENT_INN request; do not
promote or save its ordinary contents. These candidate rows must be consumed
and removed before the persisted player payload is encoded. Keep the current
depth/object/byte bounds and cycle detection effective for this traversal.

Limit the new capture context to player rent. Public list/tree capture and
pet/locker/world callers retain their existing contract. Extend the current
private traversal rather than creating an inventory-policy framework.

### 3. Retire and omit candidates atomically in each backend

Add the narrow rent-key decision to the existing item-claim module so the two
backends use the same predicate. Pass rent context only for the incoming main
player item component; never derive it from a previously stored flat-file
snapshot's old intent during a status-only or pet-only save.

In MariaDB, integrate retirement into the existing claim/apply transaction.
In flat-file, integrate it into the existing claim catalog after-image and
commit that image with the filtered player image. Create a destroyed record
for a fresh candidate UID and retire an existing active candidate. Follow
existing destruction identity, detached root/parent topology, item/owner
revision and ownership-audit conventions. Reuse current record locks and
the flat-file authority lock; do not start a nested independent transaction.

Use the existing written-item filtering/remapping path to remove the
candidates. Preserve the general claim rules for ordinary assets. A UID that
is already destroyed remains destroyed, and retrying rent does not increment
revisions or emit duplicate retirement events unnecessarily. Deliberate rent
disposal should be identifiable as such, not reported as a duplicate-item
incident; use existing persistence diagnostics, without introducing telemetry
infrastructure.

Only loaded, captured player holdings authorize retirement. Do not scan and
destroy every ownership row for a PID or prototype. Check the existing
memory-authoritative claim behavior for a stale recorded owner in a focused
test; do not invent a different ownership conflict policy just for keys.
Use the object's assigned UID; do not infer identity from its vnum or invent
another UID. Keep malformed-source handling consistent with the current
capture and repository boundaries.

Keep ownership, payload and revision changes within the single transaction on
all error paths. Keep tombstones through restart so ordinary boot reaping and
an older save cannot make the same UID claimable again. The runtime cache is
not the durable authority. Verify that terminal extraction removes the live key
and subsequent loads use durable custody; do not mutate live objects from the
writer thread. The completed inspection below explains why clearing the entire
runtime ownership domain is unnecessary.

### 4. Prove the command and persistence journeys

Add one focused `tests/async/test_norent_key_rent_journey.py` using existing
journey helpers and a backend selector. Do not add a general test framework.
Install the real Golden Hall key prototype into disposable fixtures and use
real rent commands with synthetic players and an inn. Native cases can
cover additional RENT_INN producers without duplicating a whole world setup.

For each backend, obtain a fresh key and a demonstrably hydrated owned key,
then rent and reconnect for carried, equipped and nested placement. To
establish a previously owned fixture despite today's fresh-key omission,
seed a valid synthetic owned snapshot through the backend test setup and
log in through the real loader; confirm UID and active custody before renting.
Do not mistake assigning a UID for proving ownership hydration.

Wait for the actual terminal writer result before inspecting durable state.
Check both the saved payload and ownership record, then reconnect and restart
the disposable server. Verify no key returns and bag/sibling UIDs and contents
are unchanged. An empty inventory display alone is insufficient.

Exercise crash checkpoints, copyover and their subsequent reconnect paths as
compatibility controls, with fresh and active copies. Confirm active keys
survive recovery and that fresh-key behavior matches the independently
measured baseline for the route tested. Exercise an older queued checkpoint
followed by rent, an older snapshot replayed after committed rent, duplicate
rent apply, SQL rollback and flat-file commit/recovery failure. Reuse the
existing worker and authority-transaction harnesses for deterministic faults;
do not use arbitrary sleeps as durability evidence.

### 5. Investigate the reported live instance and finish documentation

The issue supplies no reporter character or actual item UID. Locate the
original report and relevant permitted operational evidence, then correlate
the precise UID, vnum, instance type/flags, root/parent placement, runtime
custody, durable owner/state and save intent with the server that served the
report. Record its running revision/binary identity and evidence timestamps;
a current checkout revision is not proof of the running executable or of
what ran when the report occurred.

Use read-only inspection and existing diagnostics. Keep credentials, raw
player records and operational logs out of Git; record only the minimal
redacted finding in this plan/issue. No live rent, forced logout, item mutation,
migration or deployment is authorized by this planning request. If the
original object is gone or the reporter cannot be identified, state that
exact-instance attribution remains unverified and specify the missing
evidence. Do not close that acceptance item by substituting the synthetic
reproduction.

Update `docs/reference/DATABASE.md` where it explains claims/destruction with
the exact RENT_INN key exception, transaction behavior and preserved recovery
semantics. Update this plan with measured results, unresolved live attribution
and the final source revision. Reread the diff and remove speculative code.

## Files

Expected production edits:

- `src/player/player_snapshot_capture.c`: rent-specific candidate capture.
- `src/item/item_claim.h`, `src/item/item_claim.c`: the shared narrow predicate
  and, only if necessary, the existing claim result's disposal accounting.
- `src/item/item_claim_repository.h`, `src/item/item_claim_repository.c`,
  `src/player/player_snapshot_repository.c`: SQL claim context and atomic
  retirement/filtering.
- `src/flatfile/flatfile_item_repository.h`,
  `src/flatfile/flatfile_item_repository.c`,
  `src/flatfile/flatfile_player_repository.c`: the same operation in the
  existing flat-file claim/authority transaction.

Expected verification edits: the current capture, flat-file claim, MariaDB
claim, and worker/transaction harnesses where a new assertion is needed, plus
the one focused dual-backend rent journey. Existing copyover coverage should
be extended only where its current assertions miss the key's lifetime.

`player_snapshot.h`, the codec, terminal callers, loaders, runtime ownership,
copyover and `handler.c` are traced dependencies and test inputs, not automatic
production edit targets. No database migration or snapshot schema change is
currently required. If a new regression disproves that, revise this plan with
the specific boundary before adding machinery.

## Proof and completion criteria

- All six fresh/owned by carried/equipped/nested cases pass on both backends
  through rent, durable apply, reconnect and restart.
- Removed UIDs have destroyed custody and no loadable player payload. Retrying
  or replaying an older snapshot never recreates them.
- Containers, siblings, unrelated durable NORENT assets, unflagged keys and
  protected retained components keep their existing identity and behavior.
- Filtered-ancestor nesting cannot hide a key from disposal or expose ordinary
  omitted contents. Bounds and cycle rejection still work.
- Active-key crash/copyover recovery remains intact; fresh-key baseline
  limitations are documented and route-specific tests are reported honestly.
- Status-only/pet-only checkpoints and non-rent contexts do not dispose keys.
  Terminal queue ordering and failure behavior remain unchanged.
- Backend fault tests demonstrate atomic state or successful transaction
  recovery, with no premature success claim.
- Live attribution has either direct evidence or a clearly recorded unresolved
  dependency; issue closure requires resolving or explicitly dispositioning it.

Run the narrow tests as their edits land, followed by the required build:

```sh
python3 tests/async/test_player_snapshot_capture.py
python3 tests/async/test_player_save_claim.py
bash tests/async/run_player_save_claim_mysql.sh
python3 tests/async/test_player_save_worker.py
python3 tests/async/test_player_save_pipeline.py
python3 tests/async/test_flatfile_authority_transaction.py
python3 tests/async/test_terminal_save_safety.py
python3 tests/async/test_terminal_extract_item_retention.py
python3 tests/async/test_copyover_custody.py
make -C src
python3 tests/async/test_norent_key_rent_journey.py --backend flatfile
bash tests/async/with_disposable_mariadb.sh python3 tests/async/test_norent_key_rent_journey.py --backend mariadb --server bin/server/dms_new
./scripts/format.sh --check
python3 tests/async/test_documentation_contract.py
git diff --check
```

The new journey command/interface is planned, not present yet. Its flat-file
leg must use the existing isolated build helper and keep artifacts under
`bin/`; its MariaDB leg uses disposable credentials from the wrapper, never
the checkout's `.env`. No full burn-in or CI wait is needed for this scoped
change. Run additional tests only when a touched boundary or failure warrants
them, and report unavailable validation explicitly.

## Ablation decisions

Keep transaction-level disposal, both backend paths, actual reconnect proof
and live-instance attribution: each maps to an explicit issue requirement.
Keep bounded capture of candidates hidden by an omitted ancestor because the
existing early return otherwise defeats nested disposal.

Simplify by using existing snapshot fields, the existing claim/filter paths,
destroyed custody states, one writer and the flat-file authority transaction.
A small shared predicate has two actual backend consumers. Reuse current
journey helpers and existing fault harnesses.

Drop the area edit, a golden-key-only exception, removal of the general
NORENT preservation safeguard, a new schema/DTO, synchronous per-item
destruction, global extraction changes, a migration and adjacent door policy.
None is necessary for the scoped lifetime rule. The main complexity that
remains is atomic custody disposal and proving compatibility.

## Planning validation and implementation estimate

Planning evidence on the baseline:

- The standalone production capture/codec probe passed 36 cases; source and
  executable are ignored under `bin/tests/issue419-planning/`.
- Docker is available for the planned disposable MariaDB qualification.
- `python3 tests/async/test_documentation_contract.py`: all 14 tests passed.
- `git diff --check`: passed. The archived #428 plan has the same SHA-256 as
  the original: `db2e06ff1afe39dba4629cc840c579b994e04965df0e31995174625eee95fdbf`.
- No production C/C++ file changed, so a full server build and database/socket
  journeys are implementation validation, not claims made by this plan.

Estimate for **my active implementation and local qualification: 6-9 hours**:

- Regression fixtures and final transaction design: 1-1.5 hours.
- Capture and both backend changes: 2-3 hours.
- Dual-backend rent/reconnect/restart, recovery and fault qualification:
  2-3 hours.
- Required build, documentation and final review: 1-1.5 hours.

Allow **up to 12 hours** if full-world/copyover fixtures or backend fault
coverage need repair. This is an estimate, not a commitment; it excludes
external review, deployment and waiting for reporter/live-instance access.
Once that evidence is available, read-only attribution should take about
30-60 minutes, but cannot be promised without the UID or reporter context.

## Implementation and qualification, 2026-10-30

Implementation commit:
[41adafc3e5f9cea34c7c5861726d4cc42091a996](https://github.com/LuminariMUD/Duris/commit/41adafc3e5f9cea34c7c5861726d4cc42091a996).

The player RENT_INN capture includes fresh and active NORENT keys for
transactional disposal. Skipped ancestors are walked within the existing
budgets/cycle checks to collect only key candidates. Their ordinary contents
remain omitted. Capture never extracts or changes the live objects.

Both repositories use the existing claim loops to write destroyed custody under
destruction:0:0, detach each key from its former parent, and use the existing
graph filter to omit it from the saved player items. Fresh UIDs get tombstones;
already destroyed candidates remain unchanged. Ownership revisions and the
existing SQL audit / flat-file claim log record actual changes. Intentional
retirement does not produce duplicate-item warnings. SQL payload replacement
and custody commit together; flat-file catalog and player images share the
existing authority transaction.

The general durable-NORENT safeguard remains for non-keys. The rule is enabled
only for the incoming main player item component with RENT_INN; status-only
and pet-only updates cannot infer disposal from a stored intent. Quit and the
trusted camp shortcut already share that intent. No migration, snapshot-schema
change, separate disposal payload, writer job, setting, area edit or production
terminal-caller change was needed.

### Evidence and simplifications

The new capture and first flat-file rent assertions failed before the production
repair. The expanded capture/codec suite passes **56 cases**: seven intents,
fresh/active ownership, and carried/held/nested/omitted-ancestor placement.
Additional executable controls cover cycles, depth and object limits, invalid
UIDs, unchanged generic list capture, an unflagged key and an active NORENT
non-key. Failure leaves the output snapshot unmodified.

Each backend's repository suite passes all six ownership/placement cases,
container/sibling and unflagged-key controls, a stale foreign recorded owner,
identical rent replay, pre-rent snapshot replay, missing-UID rejection,
non-rent intents and partial status/pet updates. SQL failure injected at the
payload deletion boundary rolls back custody, audit and inventory together.
Flat-file faults before journal commit, after journal publication and after
the first image prove unchanged prior state or recovery of the complete
retired-key/player-image pair. The worker test proves that replacing a queued
checkpoint retains RENT_INN and the key payload together.

The new socket journey reuses existing full-world runtime, account, backend and
build helpers. It loads actual prototype 40401 and rents at Golden Hall inn
40454, using a synthetic staff PC for object setup. Inn processing and player
save/load are the real routes; staff level affects population bookkeeping,
not key disposal. All **12 cases** (six per backend) pass real rent, durable
state inspection and reconnect. A subsequent complete restart confirms every
retired UID stays absent. Backpack 48 and nested sibling 15 retain their exact
UIDs and parent placement throughout.

Owned-fixture setup was simplified from offline snapshot seeding: temporarily
clear NORENT on the isolated newly loaded key, save and rent, reconnect through
the real loader, then restore the original flag. A subsequent ordinary save
retains that flagged key, proving active runtime custody was hydrated. The
fresh fixture's ordinary save omits its key while live inventory still contains
it. The temporary flag change is fixture setup only.

Both full-world backends also pass active-key checkpoint, SIGKILL/relogin and
actual SIGUSR1 copyover controls. Fresh NORENT keys remain omitted by
checkpoint/crash/copyover, matching the baseline capture result and source:
copyover's separate world-object graph includes floor/NPC roots, not PC
inventory. This repair preserves that existing limitation.

Runtime-cache cleanup was ablated after source inspection. Ordinary hydration
updates incoming entries without clearing every historical UID. Disposal does
not require a global clear: terminal extraction removes the live object,
retired payloads are absent, loaders check durable custody, and the existing
destroyed-state rule prevents stale saves from reclaiming the UID. Same-process
reconnect and process-restart journeys prove those boundaries. No speculative
cache-reset hook was added.

Two existing harness linkage gaps blocked required checks: the save-pipeline
fixture needed a memory-free stub for its extracted toggle command, and the
no-player copyover fixture needed fail-if-called launch-gate stubs. Those
focused test repairs are included; neither changes game behavior. The
copyover fixture exercises real world-object/ownership save/exec/recover under
ASan/UBSan. PC key recovery is proven separately by the socket journey.

### Completed verification

All commands below passed. Builds use the development warnings-as-errors
profile. Logs and runtime reports are ignored under
`bin/qualification/issue419/`.

```sh
make -C src -j6
make -C src PERSISTENCE_BACKEND=flatfile SERVER_BIN_DIR=/home/aiwithapex/projects/duris-worktrees/issue-419-plan/bin/qualification/issue419/flatfile DMS_BINARY=/home/aiwithapex/projects/duris-worktrees/issue-419-plan/bin/qualification/issue419/flatfile/dms_new -j6
python3 tests/async/test_player_snapshot_capture.py
python3 tests/async/test_player_save_claim.py
bash tests/async/run_player_save_claim_mysql.sh
python3 tests/async/test_player_save_worker.py
python3 tests/async/test_player_save_pipeline.py
python3 tests/async/test_flatfile_authority_transaction.py
python3 tests/async/test_terminal_save_safety.py
python3 tests/async/test_terminal_extract_item_retention.py
python3 tests/async/test_copyover_custody.py
python3 tests/async/test_player_load_items.py
python3 tests/async/test_norent_key_rent_journey.py --backend flatfile --server bin/qualification/issue419/flatfile/dms_new
bash tests/async/with_disposable_mariadb.sh python3 tests/async/test_norent_key_rent_journey.py --backend mariadb --server bin/server/dms_new
./scripts/format.sh --check
python3 tests/async/test_documentation_contract.py
git diff --check
./scripts/tidy.sh
CLANG_TIDY=/home/aiwithapex/.local/bin/clang-tidy ./scripts/tidy.sh --staged
```

Changed Python files passed syntax checks; all 14 documentation tests passed.
The load-items regression includes retained-source hydration controls.
MariaDB was rebuilt after final header edits. The initial direct-Git commit
selected system Clang 18, which could not parse the installed GCC 16 library
headers. Selecting the installed LLVM 22.1.8 used by the passing worktree check
resolved this. The staged check and commit hook both passed, without bypass.

The socket reports `flatfile.json` and `mariadb.json` each contain
`passed: true`, six exact retired UIDs and the three recovery outcomes.
Socket-qualified binary SHA-256 values:

- Flat-file: `98dd08f58454cbca955ef5f0595f4888cf6a8850fbf88f7912e7be9a1ab09cca`.
- MariaDB: `a26136659dd1490a1c5ab44a96d9caaed72b119ead76ebd7066f3bad9eb0733b`.

Subsequent edits before the implementation commit were documentation, header
comments, test assertions/diagnostics and formatting. No server behavior
changed after these socket qualifications. No production state changed,
and no deployment or CI result is claimed.

### Original-instance attribution

The refreshed issue still contains no reporter character, actual UID or event
time and has no comments supplying them. The local report file is empty;
targeted report-history searches did not identify the incident. The owning
checkout is configured local, so its revision is not evidence of the reported
server. The user has no additional identifying information.

The original instance's flags, custody history and running revision therefore
cannot be established from available evidence. This remains an explicit
limitation; the synthetic reproduction does not prove the exact report.
The branch and PR refer to #419 without automatically closing it. The code
repair, qualification, documentation and PR are deliverable; historical
live attribution is recorded as unavailable.

## Master integration and final qualification, 2026-10-30

Qualified source commit:
[0598fb15fb83f5279977d40bbca95d9405cbea33](https://github.com/LuminariMUD/Duris/commit/0598fb15fb83f5279977d40bbca95d9405cbea33).

PR [#475](https://github.com/LuminariMUD/Duris/pull/475) initially reported a
conflict because master advanced to
`b352b650c3f05ea0c2e109eaa9abcc3040290952` during implementation. The merge
preserves master's quest snapshot version 13, new status fields and their
regressions. All production code merged cleanly. The sole conflict was the
shared plan; master's #437 plan was preserved byte-for-byte as
[plan-issue-437.md](plan-issue-437.md), SHA-256
`ec2a89006a68a4540b5b71b325ef51bb7683d568588f35b59b83b76d31ab95b4`.
The earlier #428 archive remains unchanged.

Both server builds, all nine focused Python regressions listed above, the
MariaDB claim/loader suite, both full-world socket journeys, changed-line
clang-tidy, the staged merge hook, formatting and all 14 documentation tests
passed again after integration. The 12 rent cases and active/fresh recovery
controls are therefore qualified on the merged source, not merely the earlier
branch.

The flat-file rerun exposed an inspector read concurrent with atomic snapshot
publication. The fixture now holds the existing authority lock while opening
and validating that file and reports the read result after it completes.
It does not retry arbitrary read errors or change the server. The full
flat-file journey then passed all cases and recovery controls.

The current reports `bin/qualification/issue419/flatfile.json` and
`mariadb.json` both record `passed: true`; pre-merge reports are retained in
the `premerge/` subdirectory. Repeated test/build logs have a `merged-`
or `build-merged-` prefix. Final socket-qualified binary SHA-256 values,
which supersede the earlier hashes:

- Flat-file: `5c2a9c1bc99ff93d2f349792a441f89034a27959b32a538b10be369e01f37aa0`.
- MariaDB: `20f5d9040debbaedda6eb743f29d72e4fda17403dc8b52e0ccd409fa8bde50f5`.

The #419-specific change still requires no schema migration; the merged quest
migration belongs to master. Original-instance attribution remains unavailable,
and production deployment remains outside this delivery.
