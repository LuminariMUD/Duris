# Issue #454: batch produced shop purchases into a container

Status: **implemented; PR #495 review addressed; ready to merge**.
Updated: 2026-10-30.
Issue: [Duris #454](https://github.com/LuminariMUD/Duris/issues/454).
Branch: [branch/issue-454-plan](https://github.com/LuminariMUD/Duris/tree/branch/issue-454-plan).
Source baseline: origin/master at `c9361959ceb6cb2a9004fea2c03748cef909dc3f`.
Worktree: `/home/aiwithapex/projects/duris-issue-454`.

The shared [plan.md](plan.md) remains identical to master; this issue keeps
its own implementation and qualification record to avoid cross-PR conflicts.
This plan applies the repository's [ablation skill](../../.agents/skills/ablation/SKILL.md).

## Outcome

For produced shop stock, `buy <item> <container> <quantity>` accepts 1-50 items
and delivers the admitted purchase through one ownership/trade command, with
one final completion. Its number of sequential persistence/completion stages
must not grow with the quantity. A successful 50-item request must not become
50 grants, parallel single-item commands, or five serial 12-item trades.

Preserve the useful current partial-purchase behavior: stage the largest prefix
that the player's funds and the selected container can accept, then purchase
that prefix as one batch. Report the actual count and total; unadmitted items
cost nothing. If the admitted batch is terminally rejected, none of that batch
is delivered and its full debit is returned once. Preserve trusted players'
zero-charge purchases, the current price calculation, quantity parsing,
container restrictions and normal single-item/existing-stock/sale behavior.
Success messages follow durable ownership and successful live publication.
Per-item messages may remain, emitted together from the batch completion.

Both MariaDB and flat-file persistence are in scope. Use their existing
ownership, writer, coordinator, replay and materialization paths. Wallet
application remains immediate; this work does not promise a new transaction
that atomically combines wallet saves, keeper saves and item ownership.

## Findings from the current code

These findings were checked against the baseline, independently of the issue's
historical line references and transaction-count assertion.

1. **The serial delivery defect remains.**
   `src/economy/shop.c:60-75,199-278,306-593,983-1318` stages one clone at a
   time. The MariaDB branch starts the successor only from final grant
   completion; flat-file starts it only from trade completion. Each successor
   observes the preceding item's published capacity and balance changes.
   Container syntax is available only for produced stock. Quantity is optional
   and bounded by `shop_purchase_count()` to 1-50 with no trailing arguments.

2. **The stated 100 asynchronous DB transactions is stale.**
   `src/economy/currency_transaction.c:143-256,300-313` applies a wallet change
   immediately and invokes its callback before submission returns. It does
   not queue a wallet authority transaction. Both backends use this behavior.
   Bank deltas have a separate writer path, irrelevant to this purchase.
   The relevant remaining wait is each item's creation grant or flat-file
   trade; keeper/player saves are additional writer work. Do not build the
   change around removing a payment round-trip that no longer exists.

3. **Creation batches exist, but cannot serve this command unchanged.**
   `src/item/item_movement_transaction.h:64-91` exposes only a pre-entry batch
   API. In the implementation, `submit_grant_batch()`,
   `start_creation_grant()` and `creation_grant_batch_completion()` assume
   detached roots delivered to the actor's inventory, pre-entry requests,
   starter-kit notifications and no purchase completion callback.
   The common transfer limit is 3,000 entries, so 50 empty produced roots do
   not require raising that global limit.

4. **Container topology is a real shared boundary.**
   `src/item/item_transfer_command.c:154-240` already calculates each root's
   destination, but rejects multi-root creations with an external container.
   Both `src/item/item_transfer_repository.c` and
   `src/flatfile/flatfile_item_repository.c` use that topology function and
   validate the target parent. `src/item/item_ownership_runtime.c` also uses it.
   Extend this existing path; do not bypass ownership or publish loose inventory
   first and fix the durable parentage afterward.

5. **Reconciliation must be extended with the grant API.**
   `src/item/item_movement_transaction.c:476-540,794-852` and
   `src/player/player_load_items.c:859` assume inventory-only batch recovery.
   The latter rejects target-parent/root fields outright. A container batch
   needs detached graph reconstruction followed by publication to the verified
   destination, including retained offline completions. A success callback must
   mean all admitted roots were published, not just that the writer committed.

6. **Flat-file trades represent one tree, not a shopping quantity.**
   `src/economy/shop_trade_command.h` currently has payload version 4, a
   12-entry limit and a fixed 304-byte result. `valid_payload()` in its `.c`
   requires one selected root. `shop_trade_runtime_build_payload()` captures
   one tree; the transaction publication builds a single-root item transfer.
   Merely raising the array bound would leave those assumptions incorrect.
   `src/flatfile/flatfile_shopkeeper_repository.c:365-403` independently
   requires exactly one snapshot root.

7. **The flat-file authority already has the required commit boundary.**
   `src/flatfile/flatfile_shop_trade_repository.c:275-402` commits the
   operation record, shop revision, item ownership and player materialization
   in one authority transaction. Keep that transaction for the whole batch.
   `shop_trade_transaction.c` already debits escrow and queues the buyer's
   save before submitting the trade, refunds rejected trades, and retains
   completions for absent players. Extend its publication and the existing
   materialization record instead of introducing a second shop service.

8. **Persisted result compatibility cannot be ignored.**
   `src/flatfile/flatfile_shop_trade_repository.c:38-53,136-224` stores fixed
   304-byte results in version-1 `shop_trade_operations` records. Enlarging
   `SHOP_TRADE_RESULT_BYTES` in place would make existing catalogs unreadable.
   The command codec also supports older payload versions. Preserve those
   readers and old operation IDs/digests/results when introducing batch records.
   Shared critical results already allow 8,192 bytes; this task needs no
   increase to that global bound.

9. **Capacity must be cumulative and side-effect free.**
   `shop_trade_container_accepts()` enforces closed/container, artifact/nodrop,
   weight and optional `USE_SPACE` rules. The carrying check reserves a
   temporary inventory slot per insertion, not one slot per object remaining
   inside a bag. `src/world/handler.c:115-245,2903-2984` calculates weight from
   actual contents, prototype shells and weight reductions with rounding.
   Checking every clone against the unchanged bag, multiplying a single
   effective weight, or requiring 50 free top-level slots would change behavior.

The existing `test_shop_multi_buy_sequence.py` is a source contract that
explicitly requires serial continuation. Its green result verifies the current
implementation shape; it does not establish acceptable multi-buy latency.

## Non-goals

- No command syntax, 50-item limit, stock selection, barter/epic pricing, gem
  payment policy, artifact policy or general inventory-capacity rebalance.
- No bulk purchase of finite existing stock, sales or unrelated merchant types.
- No new persistence framework, worker pool, batch scheduler, configuration
  option, per-item parallel submission or timeout-based success shortcut.
- No general currency rewrite, stronger crash-atomic money/item guarantee,
  auction/locker cleanup, new global limits or speculative SQL migration.
- No production operation, deployment, full burn-in or dependency on hosted CI.
  All runtime qualification uses disposable local/dev state.

## Files and implementation sequence

Expected production files are `src/economy/shop.c`, the existing
`shop_trade_command.{h,c}`, `shop_trade_runtime.{h,c}` and
`shop_trade_transaction.c` under `src/economy/`,
`src/item/item_movement_transaction.{h,c}`,
`src/item/item_transfer_command.c`, and the flat-file shop/item repository and
materialization files under `src/flatfile/` identified below. Inspect and adjust
`src/player/player_load_items.c` only where detached recovery needs it.
The item-transfer SQL repository and ownership runtime should keep their shared
application logic; edit them only if executable container-batch tests expose a
remaining single-root assumption. No new production module is expected.

1. **Replace the serial contract with executable purchase regression coverage.**
   Extend `tests/async/test_shop_multi_buy_sequence.py` to drive the production
   purchase/staging/completion bodies with controlled service boundaries.
   Record wallet changes, submitted commands, publication and output.
   Demonstrate that a 20/50-item request currently needs one completion per
   item. Require one admitted batch and one final callback after the change.
   Cover count 1 alongside the new path, and preserve argument-validation
   assertions that protect observable behavior. Do not retain assertions that
   mandate a per-item successor or introduce a general harness framework.

2. **Stage the deliverable prefix once in the shop command.**
   Keep stock selection and the once-per-command unit price. Clone at most 50
   objects on the game thread, assign store-item flags before snapshot capture,
   and retain their actual UIDs. Use a read-only staging view of the destination
   and the existing weight/capacity calculation to account for earlier staged
   roots, negative shells, weight-reduction rounding and optional space rules.
   Staging must not link items into the player's live inventory or dirty the bag.
   Retain the existing transient carrying-slot rule. Stop at funds/capacity
   exhaustion; allocation, capture or admission failure cleans up the staged
   unpublished objects without announcing success. Use checked 64-bit totals
   and explicit range checks at existing narrower money/payload boundaries;
   reject an unrepresentable total before charging, never wrap or truncate it.
   Revalidate the live keeper, stock, player room, destination and relevant
   ownership revisions before admission. Once committed, delivery depends on
   the owned destination and captured roots, without requiring the buyer or
   keeper to remain in the shop. One pending purchase state owns the complete
   batch; no live pointers survive asynchronous completion.

3. **Extend the existing creation batch for ordinary player/container grants.**
   Add a bounded ordinary-player batch entry point with a final completion
   callback and optional destination. Reuse `submit_grant_batch()`, the existing
   queue and coordinator; keep the pre-entry API as its existing compatibility
   entry point. Do not attach starter-kit announcements or pre-entry eligibility
   to shopping. Preserve the ownership convention: refused admission leaves all
   roots with the caller; accepted admission transfers all roots to the queue.
   Permit multi-root creation into one verified player-owned container through
   the existing item-transfer topology validation. Each source root remains a
   separate absent root; each destination root becomes a child of the same bag.
   Preserve sorted UID validation, parent fencing, graph validation, revision
   checks and serialization limits. No need to change the transfer wire layout
   solely to carry fields it already has.

4. **Make grant completion and recovery batch-aware.**
   Validate the complete graph/destination before any live insertion, publish
   all roots in one game-loop completion and verify their final locations.
   Reuse detached reconstruction for missing bodies; keep source snapshot
   topology separate from the eventual external parent. Update
   `reconcile_creation_grant_batch()` and its materialization caller/validator
   together so a committed batch is recoverable rather than discarded.
   Retain pending state on a committed publication failure. Invoke the purchase
   callback once after successful publication or terminal authority rejection,
   releasing queue state before invoking a callback that may submit more work.
   Preserve offline/reconnect handling and ordinary starter-kit behavior.
   In MariaDB shopping, apply one aggregate debit, credit/save the keeper once,
   and submit one batch grant. Refund the aggregate once only on genuine grant
   rejection/admission failure. A durable-but-unpublished grant is pending
   recovery, not a refundable failed purchase. Handle synchronous wallet
   callbacks safely; they may finish before the submit call returns.

5. **Extend the flat-file composite trade, including its stored formats.**
   Extend `buy_produced` with explicit multi-root batch semantics in a new shop
   payload version; older versions retain their single-tree interpretation.
   Carry the full staged forest, one stock exemplar, one destination and one
   aggregate price. Bound new produced batches to the command's 50 roots,
   check entry/blob sizes, and leave legacy actions' established tree limits
   intact. Extend the runtime builder/matcher, ownership publication and
   `flatfile_item_repository_prepare_shop_trade()` to use the same multi-root
   transfer topology as grants.
   Extend `trade_items_match_payload()` and produced-stock checks in
   `flatfile_shopkeeper_repository.c` to verify every root while retaining the
   exemplar and shop-revision checks. Advance the shop revision once, leaving
   its produced exemplar in stock. Extend
   `flatfile_shop_trade_materialization.c` only where its single-root checks
   require it; persist all created snapshots and actual bag parentage together.
   Introduce a versioned result that can identify all batch items, within the
   existing critical result bound. Give the operation catalog a versioned,
   length-aware record encoding; read its existing version-1 fixed results
   unchanged. Preserve original command digests and result bytes/lengths when
   carrying old operations forward. Use the existing guarded authority writer
   for the first new-format write; no manual rewrite or wipe of old state.

6. **Route both backends and remove the obsolete serial state.**
   Submit one flat-file trade for the admitted batch, using its current escrow,
   save ordering and operation replay semantics. Credit the keeper once and
   publish every produced root only after successful committed validation.
   Verify every returned UID/count against the admitted batch before success.
   Preflight every live root/destination before advancing runtime ownership or
   shop revisions. Extend the existing pending/reconnect path to retain a
   committed batch until full publication succeeds; retries must apply each
   revision and keeper credit only once. The current transaction erases pending
   state before its shop callback, so that boundary needs explicit coverage.
   Preserve the distinction between authority rejection and committed live
   publication failure. Emit accurate pending/recovery wording for the latter;
   never say uncharged or refund a batch whose items already committed.
   Remove per-unit successor functions and `current_item_uid`/remaining-payment
   state made obsolete by batching. Retain only state required for the batch,
   aggregate accounting and final requested/delivered summary. Route ordinary
   count-one produced purchases through the same logic where practical; keep
   finite-stock, sale and invalid-stock cleanup behavior unchanged.

7. **Qualify the real command and persistence paths, then document.**
   Extend the existing codec, transfer, grant reconciliation, shop transaction
   and flat-file repository tests rather than creating parallel infrastructure.
   Replace stale route assertions in `test_shop_trade_live_route.py`.
   Add one focused shop multi-buy journey using existing socket/world helpers
   from `test_flatfile_combat_journey.py` and the disposable backend setup in
   `test_flight_network_journey.py`; use the SQL setup approach demonstrated by
   `test_mysql_locker_grant_journey.py`. Exercise both backends with prepared
   mortal shoppers, sufficient funds, a produced ration and a carried bag.
   Register any new journey in the existing runner's applicable resource/manual
   category. Check the maintained BUY help entry and update it only if the
   resulting quantity/partial/pending wording needs explanation. Record exact
   commands, results and remaining limitations in this plan.

## Proof and acceptance

- Requests for 1, 2, 12, 13, 20 and 50 items deliver exactly that many unique
  produced roots when affordable and fitting. A 50-item request has one item
  authority operation, one aggregate debit/keeper credit, and one final
  purchase completion in each backend. The stock exemplar remains unchanged.
- A shopper who can afford 7 of 20 gets 7 in one batch and pays exactly 7 unit
  prices. A bag fitting only 3 gets 3. A zero-prefix request changes nothing.
  Trusted shoppers pay zero. Confirm both exact-fit and one-item-over cases,
  existing bag contents, negative/reducing shells, zero-weight items and the
  enabled space configuration. Keep the current single insertion-slot rule.
- Missing/wrong/closed containers, invalid quantities, extra arguments,
  restricted items, cloning/capture failure and admission rejection produce
  no unintended debit, delivery, dirty destination or leaked detached object.
  Large totals are handled explicitly without overflowing narrow interfaces.
- Delayed completion publishes nothing early. Terminal rejection returns the
  entire aggregate debit once and cleans up all unpublished roots. Duplicate
  completion/replay produces neither a second debit/refund nor extra items.
- An extracted clone, unavailable keeper or changed destination during the
  wait cannot yield partial live success or an incorrect refund after commit.
  Reconciliation retains/reconstructs committed roots and reports pending work
  honestly. Disconnect/reconnect releases the correct retained completion.
- Repository tests replay one batch operation before and after restart and
  inject failure around its authority commit. Assert actual ownership and bag
  parentage, all UIDs, materialized snapshots, shop revision, and idempotency.
  Open a genuine version-1 shop operation catalog, append a new batch, reopen
  and replay both old and new operations without changing the old result.
- A real `buy ration bag 20` and `buy ration bag 50` completes through command
  dispatch in both backends; inspect inventory, container, balances and durable
  ownership. Clean restart retains the completed purchase and correct count.
  Preserve existing starter/pre-entry grants, count-one inventory/container
  purchases, finite-stock buying and selling with focused controls.
- Compare baseline and changed command-to-final-response durations and the
  actual command/completion counts for 1/20/50. Acceptance is constant
  authority stages, no per-item completion dependency, and correct delivery;
  use timings as evidence, without a machine-dependent millisecond gate.
  A fast wallet/helper test alone cannot prove the gameplay improvement.

Planned focused commands after implementation (extend these existing tests):

    python3 tests/async/test_shop_multi_buy_sequence.py
    python3 tests/async/test_shop_trade_command.py
    python3 tests/async/test_shop_trade_runtime.py
    python3 tests/async/test_shop_trade_transaction.py
    python3 tests/async/test_shop_trade_live_route.py
    python3 tests/async/test_item_transfer_creation_batch.py
    python3 tests/async/test_creation_grant_batch_submission.py
    python3 tests/async/test_creation_grant_reconciliation.py
    python3 tests/async/test_player_load_items.py
    python3 tests/async/test_currency_in_memory.py
    python3 tests/async/test_flatfile_shop_trade_repository.py
    bash tests/async/run_item_transfer_schema_mysql.sh
    make -C src
    make -C src PERSISTENCE_BACKEND=flatfile DMS_BINARY=/home/aiwithapex/projects/duris-issue-454/bin/server/dms_issue454_flatfile
    ./scripts/format.sh --check
    python3 tests/async/test_documentation_contract.py
    git diff --check

The new journey must run against both freshly built backend executables using
its documented backend/server arguments. Its exact command belongs in the
implementation record once the runner exists. Keep all compiled artifacts and
qualification output under `bin/`; configure `TMPDIR` there for older harnesses
that create temporary executables. Use disposable databases/accounts and isolated
ports, without sourcing production credentials. Report unavailable runtime or
SQL evidence as unverified; source-text assertions are not a substitute.

## Ablation decisions

Keep the two existing authority routes because flat-file shops commit shop and
materialization state together, while MariaDB produced purchases use creation
grants. Share staging and item-transfer topology rather than forcing one backend
through the other's authority. Reuse existing grant batches, callback retention,
repository transactions and journey helpers. These directly supply the requested
batch behavior and protect its accounting and delivery.

Drop parallel per-item submissions and 12-item chunk continuations: both retain
unnecessary operations, and the latter retains quantity-dependent waits. Drop a
new generic batch service, currency schema, global capacity-policy rewrite,
worker tuning, new configurable limits and a standalone benchmark project.
Keep the small format-compatibility and reconciliation work: omitting either
would break existing stored operations or committed container purchases.
No alternative implementation or full-system test campaign is needed.

## Tracking and my implementation estimate

#454 is the work item for this branch; its issue has no comments or child work
items at planning time. The search for open PRs mentioning 454 returned none.
Link this branch in the issue's Development section and add the committed plan
link to the issue. This planning commit references #454 without closing it.
A later implementation PR should use the issue-closing reference only when the
full outcome above is implemented and qualified. Historical test comments
mention #537; that text alone is not evidence for a second work item to link.

Estimate: **6-9 hours of my active implementation and qualification time**.
Allow roughly 1 hour for staging and purchase regression coverage, 1.5-2 hours
for container grants/recovery, 1.5-2 hours for flat-file batching and old-format
compatibility, and 2-4 hours for both builds, executable repository checks,
command/restart journeys, documentation and final reviewable commits.
Allow up to 12 hours if disposable SQL/world fixtures expose further recovery
assumptions. This excludes external review, merge waiting and deployment.
It is based on the code paths above, not a human developer's multi-day estimate.

## Planning verification

Completed before writing the plan:

- `python3 tests/async/test_shop_multi_buy_sequence.py`: passed; existing source
  contracts confirm the current serial implementation, not a fixed purchase.
- `TMPDIR=.../bin/tests python3 tests/async/test_shop_trade_command.py`: passed;
  executable command-codec checks cover the existing bounded/legacy formats.
- `python3 tests/async/test_currency_in_memory.py`: passed under ASan/UBSan;
  executable production currency code confirms synchronous wallet completion.

Planning completion checks:

- `python3 tests/async/test_documentation_contract.py`: all 14 tests passed.
- `git diff --check`: passed after normalizing the new document to UTF-8/LF.
- The preserved #420 record and baseline `plan.md` have identical Git blob IDs:
  `d4535873615f04c54bc9c7507e9eeda4b047f37f`.
- `gh issue develop 454 --repo LuminariMUD/Duris --list` confirms the native
  Development association with `branch/issue-454-plan`.
- Only the requested plan and the intact historical archive are changed. The
  original master checkout and the other pre-existing worktree are preserved.

No server build, booted-shop reproduction, new batch implementation or measured
gameplay latency is claimed at this planning stage. Commit/push verification
and the published plan pointer are supplied in the handoff and issue comment.


## Implementation and qualification, 2026-10-30

Produced purchases now stage their affordable/fitting prefix before charging,
then use one ordinary creation batch (MariaDB) or one composite shop trade
(flat-file). Both routes retain the once-per-command unit price and settle an
aggregate amount. The serial successor functions and per-unit payment state
are removed. The ordinary grant API shares the existing bounded batch queue
with starter grants, including one final callback and a verified container
postcondition. Callback context and pending purchases retain UIDs, not live
object pointers. Free and zero-delivery summaries explicitly say "no charge".

The shared reconstruction function materializes the captured source forest
as detached roots, then its caller publishes the durable destination. This
keeps the existing player materializer's source validation intact. Missing
bodies, temporarily unavailable destinations and offline completions remain
recoverable; a committed-but-unpublished purchase is never refunded as a
rejected purchase. Native tests exercise actual shop preparation with a lost
keeper, moved bag and missing clone, plus controlled reconstruction refusal
and retry. The real grant queue is separately exercised with its target absent
at commit, restored on player-ready, exactly one final callback and no early
publication. The existing artifact regression executes shared reconstruction
and verifies UID preservation, rollback, displaced bodies and canonical state.

Flat-file batches use payload version 5, version-2 results and a length-aware
version-2 operation catalog. Payloads 1-4 and fixed version-1 catalog records
remain readable, including their original operation digests and result bytes.
A historical-layout fixture is opened, appended through the current writer and
replayed unchanged. New 50-root trades survive an interrupted authority commit,
advance the shop once and preserve the produced exemplar byte-for-byte, including
its custody revision and children. Replayed completions do not charge, refund,
publish ownership or credit the keeper twice. Legacy item-transfer destruction
semantics are retained while permitting container destinations for creations.

### Required repair exposed by the free-purchase journey

The first full-world journey exposed an existing authority defect that would
block this plan's trusted free-purchase acceptance. A free purchase into a fresh
Studio-loaded bag skipped the buyer-save step. `claim_catalog_item()` could then
invent an unknown target parent with VNUM zero, serialize it and leave the whole
ownership catalog unreadable on the next save (EILSEQ/84).

The repository regression reproduced this before the repair: an unknown parent
was committed. It now refuses that parent with ESTALE and verifies that existing
custody remains readable. Free produced-container purchases queue the same full
buyer snapshot as paid trades before submitting their authority operation. A
real free purchase into a freshly loaded bag now completes, both characters save
successfully and cold restart preserves the ordinary purchases. This uses the
existing writer ordering, with no new payload metadata, fallback or service.

### Gameplay and persistence evidence

Both maintained backends pass the real command journey in a disposable full
world. It creates mortal and staff accounts, uses an actual registered shop,
executes `buy ration bag <quantity>` for 1/2/12/13/20/50, and counts committed
authority operations. Every admitted request uses exactly one operation.
Partial-funds and partial-capacity requests deliver 7/20 and 3/20 respectively
with exact aggregate charges. Invalid quantities and a closed bag change neither
balance nor authority count. Single inventory purchases, produced-item sales,
finite-stock selling/buying and trusted zero-charge purchases also pass.

The journey verifies all 108 retained ration UIDs and their 105/3 split between
two bags, then cold-restarts the server and compares the full saved inventory
and wallet. MariaDB checks both custody parentage and physical `player_items`
container links. Its inventory query joins saved physical rows to custody:
legacy sales can leave historical custody-only rows, which are not carried
inventory. Fixture containers are saved and reloaded before SQL purchases to
use normally hydrated ownership, preserving the existing SQL grant admission
policy rather than changing Studio LOAD/GIVE semantics.

Minimal mode skips shop registration. The journey therefore makes a private
copy of full-world sources, inserts fixture prototypes in VNUM order and builds
world/lookup outputs only inside that disposable runtime. It never modifies
checkout area outputs or uses the checkout's `.env`. The new journey is
registered as resource-intensive in the existing regression runner.

The disposable MariaDB matrix additionally commits and replays 50 sibling
creations under one existing bag. An injected trigger rejects physical
materialization midway through a second 50-root command: all custody rows,
physical rows and ledger entries roll back, and both owner revisions remain
unchanged. Flat-file tests separately inject an interruption between authority
after-images and recover all 50 roots with their actual bag parentage.

### Measured baseline comparison

A temporary detached checkout of `c9361959c` supplied unchanged baseline
executables for the same private shop fixture. Both baseline journeys verify
per-item operation counts and wait for the purchase's own final receipt and
prompt, rather than using a following score response as completion evidence.

- Flat-file baseline, 1/20/50 items: 0.745/5.492/13.249 seconds and 1/20/50
  authority operations.
- MariaDB baseline, 1/20/50 items: 0.719/5.458/13.460 seconds and 1/20/50
  authority operations.
- The implementation completes these quantities in roughly 0.7-1.0 seconds
  in both backends, always with one authority operation. Quantities 12 and 13
  also pass, crossing the former shop entry bound without chunk continuations.

These are local observations, including receipt/prompt latency, not a timing
SLO. Exact delivery, balances, identities, parentage and constant authority
stages are the acceptance gates. Reports and binary hashes are retained under
`bin/qualification/issue454/` in `baseline-*-journey.json`,
`flatfile-journey.json` and `mariadb-journey.json`. No benchmark service or
production instrumentation is added. The temporary baseline checkout and its
one-off driver are removed after qualification; reports retain the evidence.

### Completed checks

All planned focused commands passed. Older harnesses were run with
`TMPDIR=/home/aiwithapex/projects/duris-issue-454/bin/tests` so their temporary
executables remain under `bin/`.

    python3 tests/async/test_shop_multi_buy_sequence.py
    python3 tests/async/test_shop_trade_command.py
    python3 tests/async/test_shop_trade_runtime.py
    python3 tests/async/test_shop_trade_transaction.py
    python3 tests/async/test_shop_trade_live_route.py
    python3 tests/async/test_item_transfer_creation_batch.py
    python3 tests/async/test_creation_grant_batch_submission.py
    python3 tests/async/test_creation_grant_reconciliation.py
    python3 tests/async/test_player_load_items.py
    python3 tests/async/test_currency_in_memory.py
    python3 tests/async/test_flatfile_shop_trade_repository.py
    bash tests/async/run_item_transfer_schema_mysql.sh
    make -C src -j6
    make -C src PERSISTENCE_BACKEND=flatfile DMS_BINARY=/home/aiwithapex/projects/duris-issue-454/bin/server/dms_issue454_flatfile -j6

Additional focused checks passed: `test_flatfile_item_repository.py`,
`test_item_movement_prompt_runtime.py`, `test_newbie_grant_lifecycle.py`,
`test_item_movement_input_queue.py` and `test_artifact_creation_admission.py`.
The shop, grant/prompt, currency and artifact native fixtures use ASan/UBSan.
Source contracts remain routing guards; the executable repositories and real
command journeys supply the behavioral/persistence evidence.

Fresh object directories were used for complete qualification builds, with
warnings treated as errors, then each corresponding executable drove its leg:

    make -C src -j6 OBJDIR=/home/aiwithapex/projects/duris-issue-454/bin/objects/server/mariadb/issue454-qualified DMS_BINARY=/home/aiwithapex/projects/duris-issue-454/bin/server/dms_issue454_mariadb_qualified
    make -C src -j6 PERSISTENCE_BACKEND=flatfile OBJDIR=/home/aiwithapex/projects/duris-issue-454/bin/objects/server/flatfile/issue454-qualified DMS_BINARY=/home/aiwithapex/projects/duris-issue-454/bin/server/dms_issue454_flatfile_qualified
    python3 tests/async/test_shop_multi_buy_journey.py --backend flatfile --server /home/aiwithapex/projects/duris-issue-454/bin/server/dms_issue454_flatfile_qualified
    bash tests/async/with_disposable_mariadb.sh python3 tests/async/test_shop_multi_buy_journey.py --backend mariadb --server /home/aiwithapex/projects/duris-issue-454/bin/server/dms_issue454_mariadb_qualified

Final working-tree gates passed: changed-line formatting, changed-line
clang-tidy, Python syntax and regression discovery, all 14 documentation
contracts and `git diff --check`.
The host's LLVM 18 parser cannot consume its default GCC 16 standard headers.
The existing `CLANG_TIDY` override binds the installed parser to installed GCC 13
headers for analysis; production builds remain GCC 16. The local wrapper is:

    exec /usr/bin/clang-tidy-18 --extra-arg=--gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13 "$@"

No checks, warnings or commit hooks are disabled. The ordinary wrapper and the
staged commit check use the same toolchain selection. Both maintained builds
leave `USE_SPACE` disabled (`actobj.c` defines it as zero; shop.c has no enabled
definition), so there is no supported space-enabled runtime to qualify. Its
existing guarded check remains intact; all active weight rules are exercised.

Ablation retains shared staging, the existing two authority routes, one reused
reconstruction path and the minimal stored-format compatibility work. It drops
serial continuations, duplicate per-unit payment state, unnecessary publication
flags and ineffective moves. No global limits, SQL schema, general currency
policy or production boot behavior change. Production data and credentials were
untouched; runtime accounts, snapshots and generated world outputs stayed in
disposable test state. No migration files, deployment or full burn-in are added.
Issue #454 remains the tracking item; commit/push and PR publication are reported
in the handoff. The shared #420 record in `plan.md` remains byte-identical to
master; the temporary duplicate archive is removed.

## PR #495 review qualification

Both review findings were reproduced in the executable shop harness before
their repairs. `shop_produced_prepare()` rejected a committed batch after the
buyer moved to another room. `shop_produced_completion()` left a cleared
descriptor prompt flag unchanged. The transaction removes its pending entry
before calling this completion, so restoring the flag there releases the final
prompt for both successful delivery and terminal rejection.

Committed preparation now checks the carried destination and captured item
graph without looking up the keeper or comparing rooms. Shop admission still
uses the existing controls. The harness covers relocation, an absent keeper,
exactly-once completion, rejection/refund, and a temporarily missing bag that
continues to defer publication without prompting until its safe return.
The existing socket journey also exercises the legacy SMARTPROMPT flag through
staff SETBIT, since its player toggle is retired, and requires the purchase's
own prompt and Telnet GA before sending any further input.

The changes reuse the existing callbacks and fixtures. No relocation fence,
new retry state, timing hook, or prompt abstraction is needed. This issue's
record now lives in `plan-issue-454.md`; `plan.md` is restored to master so
the PR does not replace another issue's handoff.

Local commands for this review pass:

    python3 tests/async/test_shop_multi_buy_sequence.py
    python3 tests/async/test_shop_trade_transaction.py
    python3 tests/async/test_shop_trade_runtime.py
    python3 tests/async/test_shop_trade_command.py
    python3 tests/async/test_shop_trade_live_route.py
    python3 tests/async/test_flatfile_shop_trade_repository.py
    python3 tests/async/test_item_movement_prompt_runtime.py
    python3 tests/async/test_creation_grant_batch_submission.py
    python3 tests/async/test_creation_grant_reconciliation.py
    python3 tests/async/test_item_transfer_creation_batch.py
    python3 tests/run_regression_tests.py --jobs 3 --match newbie_kit
    python3 tests/async/test_newbie_grant_lifecycle.py
    make -C src -j6
    make build-production -j6
    make -C src PERSISTENCE_BACKEND=flatfile OBJDIR=/home/aiwithapex/projects/duris-issue-454/bin/objects/server/flatfile/issue454-qualified DMS_BINARY=/home/aiwithapex/projects/duris-issue-454/bin/server/dms_issue454_flatfile_qualified -j6
    ./scripts/format.sh --all --check
    CLANG_TIDY=/home/aiwithapex/projects/duris-issue-454/bin/tidy/clang-tidy-gcc13 ./scripts/tidy.sh
    python3 tests/async/test_compiler_warning_profile.py
    python3 tests/async/test_documentation_contract.py
    make security-check
    npm ci --prefix site
    npm test --prefix site

These passed: all ten focused fixtures, the three newbie-kit contracts and
grant lifecycle check, both backend builds and the production profile, all
1,171 C/C++ files' formatting, changed-line clang-tidy with the GCC 13 header
selection above, 14 documentation contracts, the security source/SBOM contracts,
and all 15 site tests. Local security contracts do not constitute a CodeQL or
Trivy vulnerability scan; those hosted scanners were not run locally. The
unrelated repository-wide regression suite was not repeated for these callback
repairs. Production state and all other worktrees remain untouched.

Both real command/save/cold-restart journeys also passed using the rebuilt
executables. Each verifies eight purchases (including partial funds/capacity),
one authority operation per admitted batch, smart-prompt text and Telnet GA
without further client input, and all 108 retained ration UIDs, bag parentage
and wallet after cold restart:

    python3 tests/async/test_shop_multi_buy_journey.py --backend flatfile --server /home/aiwithapex/projects/duris-issue-454/bin/server/dms_issue454_flatfile_qualified --report /home/aiwithapex/projects/duris-issue-454/bin/qualification/issue454/review-flatfile-journey.json
    bash tests/async/with_disposable_mariadb.sh python3 tests/async/test_shop_multi_buy_journey.py --backend mariadb --server /home/aiwithapex/projects/duris-issue-454/bin/server/dms_new --report /home/aiwithapex/projects/duris-issue-454/bin/qualification/issue454/review-mariadb-journey.json

The PR is rebased onto master `0bec1dbae` without conflicts. Planning,
implementation and review fixes are squashed into one changeset; the original
`8dd6c162e` head remains in local `branch/pr495-before-review-20261030` for
recovery. No dependent stack or release tag is needed. Publishing uses an
explicit lease on the original remote head, preserving concurrent changes.
