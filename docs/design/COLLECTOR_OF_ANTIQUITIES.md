# Collector of Antiquities

Specification: [discussion #336](https://github.com/Community-Duris/Duris/discussions/336).

**Status: implemented on both backends, behind `collector.enabled` (off by default).**
Player deaths are enrolled with captured policy, live collector commands and the due
worker submit through the critical command coordinator, and protected collector NPCs
reconcile in registered auction rooms. SQL and flat-file authorities both preserve exact
item payloads, custody, currency, replay, restart, and publication boundaries. Live
journeys cover intake only ([Before enabling](#before-enabling)).

## Implemented policy

`src/economy/collector_policy.{h,c}` supplies deterministic, side-effect-free
transition decisions for candidate, collected, available, purchased, cancelled,
and expired records. Rules are copied at enrollment. Defaults are disabled,
twelve hours to collection, twenty-four hours to availability, seven days of
holding, 200 percent of stored base value, and a one-gold minimum. Money uses
the existing economy's copper units; 100 copper equals one gold. Fractional
copper is rounded upward. Bags and contents must be priced individually by
the transaction layer, using each item's own `cost`.

Collection checks both listing and observed item revisions. It allows a newer
item revision after environmental movement only when the caller has verified
active, unclaimed current custody. Activation starts the holding period at
actual activation, including late processing. Purchase checks beneficiary,
capacity, funds, and expiry. Terminal records cannot reactivate; a later death
must use a new listing and death operation. Paused listings cannot be bought
or expired, overdue listings cannot enter pause, and resumption preserves their
remaining holding time. Cancelling an item already held by the collector advances
its item revision so the eventual transaction cannot reuse stale custody state.

The indexed due queue leases at most the caller's requested batch size until an
explicit retry time. This keeps a repeatedly failing deadline from occupying the
head of every batch while preserving automatic retry after the lease. Commit
publication replaces its deadline or removes a closed listing. The queue and its
ephemeral leases can be reconstructed from current records; neither is a durable
store.

`src/economy/collector_codec.{h,c}` now defines the canonical version-one
collector catalog metadata image: a revisioned catalog, monotonic next-listing
cursor, strictly ordered records, fixed-width little-endian fields, and packed
death operation IDs. Encoding and decoding validate the defined
state/timing/pause/reason invariants, reject unknown versions and noncanonical
input without partially publishing output, and cap catalogs at 262,144 records.
This establishes the shared persistence boundary used by both the SQL and
flat-file authorities. The flat-file repository stores the same canonical
metadata, item snapshots, death enrollment, operation receipts, and result
images inside its crash-recoverable authority transaction.

These functions mutate a proposed record only. **A successful policy decision is
not proof of a committed item transfer or wallet debit.** Operation-ID replay,
atomicity, payload preservation, privacy at command dispatch, and real custody
must be implemented by the service and repositories below.

`src/economy/collector_command.{h,c}` defines the version-one critical-command
boundary for collection, activation, purchase, expiry, cancellation, pause, and
resume. Collection commands fence the complete current corpse or room root even
though only the selected item enters collector custody. This gives repositories
enough evidence to reject an incomplete root, detach a bag without taking its
excluded or later-added contents, and deterministically repair the topology that
remains. Purchase separately carries the listing revision, collector and player
owner revisions, and exact item revision. The price leaves the buyer's wallet in
memory when the purchase is submitted, and a refusal gives it back (see
[Money lives in memory](../persistence/CRITICAL_COMMAND_PIPELINE.md#money-lives-in-memory));
the repositories no longer read or write the wallet, so the wallet and bank
revisions the payload still carries are not checked. Successful fixed-size results contain the complete canonical record
for due-queue publication and remain well below the coordinator's result limit.
`collector_transaction.{h,c}` submits this command through the critical-command
coordinator, retains interactive completions across disconnect/reconnect, and
publishes committed custody, currency, and catalog results idempotently. The
collector service, maintenance worker, and flat-file repository all build and
consume these payloads through the same boundary.

The ownership contract now reserves append-only owner type 10 for collector
listings and maps it to a dedicated critical-command fence key. SQL checks,
fresh bootstrap, player recovery validation, and the ownership audit lookup all
recognize that namespace. The legacy shopkeeper widening step remains monotonic
through type 10, so a later full migration rerun cannot narrow live collector
rows. The generic item-transfer command deliberately rejects collector owners
and collector-only ledger reasons: admitting them there would update ownership
metadata without atomically updating the source object store and catalog. Only
the dedicated collector transaction described below may cross that boundary.

## Implemented authorities and runtime publication

`0018_collector_catalog` adds a revisioned singleton catalog cursor, canonical
per-listing metadata and exact item payload storage, death hint state, an
immutable collector ledger, and reconciliation quarantine evidence. The SQL
collector repository executes collect, activate, purchase, expire, cancel,
pause, and resume inside the caller's critical-operation transaction. Collection
rechecks the complete source root, detaches only the selected shell, reparents
its children, preserves the exact singleton item snapshot, and transfers its UID
to collector custody. Purchase atomically verifies capacity admission and the
listing and catalog revisions, records the price in the collector ledger (the
buyer's coins change in memory, not here), restores the exact player-item rows,
and transfers custody to the permanent beneficiary. Expiry and held-item cancel
move the UID to terminal custody. The repository emits the canonical result to
outbox destination 11 before the encompassing transaction commits.

`collector_runtime.{h,c}` maintains the game-thread catalog map, private
beneficiary listing projection, available count, and leased due index. Startup
and five-minute reconciliation load one bounded, streaming SQL statement off the
game loop. That statement validates every denormalized listing field against its
fixed-width record and cross-checks every collected/available listing against
the exact collector owner row and owner revision. Game-thread publication first
stages the complete catalog, then atomically replaces only the collector-owned
portion of the ownership runtime; unrelated player, corpse, room, and locker
custody is preserved. A snapshot older than an outbox publication is discarded
and retried rather than rolling runtime backward.

`collector_listing_pipeline.{h,c}` supplies the bounded asynchronous read path
needed by inspect and buy preparation. It admits at most 64 active requests and
64 completions, rejects duplicate IDs, supports cancellation, fences malformed
or mismatched replies, and never carries live game pointers. SQL detail reads
are non-locking and cap the exact item-blob projection; commands will revalidate
the returned record and payload under the durable transaction locks before any
mutation.

## Before enabling

`run_mysql_collector_intake_journey.py` (in `make test-db`) and
`test_flatfile_collector_intake_journey.py` drive a real death and the collection of an
antiquity from the live corpse, with shortened timers. No live journey yet covers sale
activation, inspection, purchase, save and reconnect, or expiry; the
harnesses below cover them against the repositories. Keep the feature disabled on a
server until that journey has run there.

Treat a failed live publication as a recovery signal: durable authority state remains
canonical, the cache invalidation and outbox path must reconcile it before another
action is admitted, and operators should inspect the health, quarantine, and age
metrics.

An item a mobile or pet takes from a corpse is not collected: collection looks
for the live item, and one no longer in the player's corpse counts as claimed.

## Validation and promotion evidence

Run `python3 tests/async/test_collector_policy.py` for executable policy tests and
`python3 tests/async/test_collector_codec.py` for canonical codec, corruption,
round-trip, and 100,000-record rebuild coverage. Together they cover boundary
times, delayed activation, independent cancellation, repeated-death records,
stale revisions, beneficiary checks, funds/capacity failures, terminal conflicts,
arithmetic overflow, pause/resume, strict catalog validation, and bounded indexed
leased scheduling without head-of-line starvation. They are not repository or
in-game tests.

Run `python3 tests/async/test_collector_command.py` for command/result round trips,
canonical fence reconstruction, malformed topology rejection, distinct wallet
and owner revision evidence, metadata-only transitions, held-item cancellation,
and the maximum 3,000-row source-root boundary. It proves the transaction input
contract, not a durable collector mutation.

Run the collector-focused regression set for catalog/cache publication,
transaction completion behavior, and the bounded listing pipeline. Run
`tests/async/run_collector_repository_schema_mysql.sh` only against a disposable
database: its real MariaDB journey covers empty and populated restart bootstrap,
held-custody validation, corruption rejection with strong output guarantees,
exact blob reads, source-tree shell detachment, wallet debit, player restoration,
terminal custody, operation replay, and all seven lifecycle actions. Complete
MariaDB and flat-file builds remain required after every integration change;
the flat-file collector journey exercises the corresponding authority and
recovery paths directly.

Run `python3 tests/async/test_item_transfer_codec.py` for the collector
ownership/fence codec boundary. Run
`tests/async/run_collector_item_owner_schema_mysql.sh` against its default
MariaDB image and again with `COLLECTOR_OWNER_DB_IMAGE=mysql:8.0`; the isolated
upgrade test proves type-9 preservation, type-10 admission across all three
ownership authorities, type-11 rejection, exact rerun behavior, and protection
against a later shopkeeper-migration narrowing pass.
