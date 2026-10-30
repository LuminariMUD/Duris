# Epic stone reward recovery

Ordinary SQL stone touches submit a version-2 zone transaction containing the
captured participant amounts, including task and bonus modifiers. The SQL
transaction commits participant epic ledgers, the stone claim, and outbox
receipts together, plus zone history when `record_zone` is set. A terminal
failure rolls back those writes.

Current source also has prepared delivery for flatfile and Divine-mode awards,
with durable recipient receipts and saved delivery watermarks. See
[Epic tasks: zone runestones](../reference/EPIC_TASKS.md#zone-runestone) and
`divine_boon_delivery.c` for that path. The process-local effect limits below
describe ordinary, unprepared SQL delivery.

The game keeps a pending reservation for the stone and ordinary zone. Rejection
leaves the stone and tasks unchanged; uncertain outcomes retain that reservation
for coordinator recovery. On a successful readable receipt,
`epic_finish_stone_touch()` discharges the stone and publishes the zone result
before participant delivery. For unprepared SQL delivery, online participants'
in-memory balances are increased and marked dirty before errand, boon, and level
effects run. Offline participants wait in the pending map until reconnect in
the same process. Player checkpoints write those balances; the ledger alone
does not restore an unpublished balance.
The 64-operation admission limit counts only uncommitted transactions. Completed
receipts remain in memory until their offline recipients return; they do not block
new touches. The participant limit is 15 per touch. This retained backlog can
grow during the process lifetime. Artifact and guild dispatch also occurs on
reconnect, and level eligibility uses the
captured stone level even after the object is removed.
Humming and touch feedback both honor zone eligibility and pending work.

The SQL `epic_stone_claim` table uses the globally allocated object UID, rather
than a zone/boot counter. Re-touching a surviving claimed stone returns its
original receipt and discharges the stone without another award. A newly
loaded stone has a new UID.
This also protects against a lost callback after the claim commits. New
recovery requests receive their own outbox receipt so reconciliation stays clean.

If a committed receipt cannot be decoded or does not match the captured stone,
the game reports that the receipt is unavailable and retains the reservation.
This requires staff investigation; a fresh award is not a safe substitute for
reconciling the original operation.

## Compatibility and rollout

- Apply immutable migration `0012_epic_stone_claim` through the standard migration
  runner before starting this binary. Fresh bootstrap includes the same table.
- The [data-lifecycle policy](../../migrations/data_lifecycle_manifest.json)
  classifies claims as replay records to retain across season resets. Preserve
  their operation-inbox proof; never delete claims or recycle object UIDs independently.
- Version-1 zone commands and old 88-byte receipts remain metadata-only;
  older version-2 receipt envelopes are 512 bytes. The current encoder writes
  1024-byte envelopes, including for version-2 payloads, and the decoder accepts
  all three sizes. The codec reads prepared version-3/4 commands; version 4
  includes artifact intents. Retain a recovery binary compatible with the
  commands/receipts actually written and the current
  migrations, including `0012_epic_stone_claim`.
- Flatfile accepts prepared zone touches through its player-domain repository.
  Unprepared flatfile commands are rejected; balance support alone does not
  establish task-zone catalog availability. See the
  [epic-task catalog boundary](../reference/EPIC_TASKS.md#task-zone-catalog-and-readiness).
- This does not reconstruct awards lost by older code.

## Verification and limits

`test_epic_stone_transaction.py` tests codecs and, when explicitly enabled against
a disposable fixture, solo/group awards, metadata-only v1 compatibility, operation
replay, same-UID recovery, and rollback after participant, outcome, outbox and inbox
failures. `test_epic_stone_runtime.py` exercises production transaction orchestration
with controlled admission, terminal/ambiguous completions, disconnects and recovery.

Durable claim and ledger history do not depend on a live player or object.
Unprepared SQL delivery still keeps unpublished balance additions and secondary
gameplay effects in process memory. Recovering a claim prevents another award
but does not replay those player effects after a process crash. Prepared
delivery instead uses its recipient receipt sequence and saved watermark.
These codec/runtime checks alone do not establish full process-kill/copyover or
live-game recovery. SQL rollback
and replay checks use synthetic data, not production data.
