# Locker identification

Paid locker `stat <item>` captures the selected item's description and charges the configured copper value from the wallet, in memory; the player's save writes it. It does not add a fixed recovery timer or clear existing combat/skill waits. Ordinary lore and legend-lore recovery remain unchanged. Fighting, ownership and level-based identification restrictions are checked before accepting the request.

The captured description belongs to the selection at request time. Renaming, moving or extracting that item while payment is pending does not change the purchased description. The deferred service retains no object or character pointers.

## Payment and replay

The service first writes a prepared receipt containing the captured text and the complete currency command: operation ID, timestamp, account, player ID, racewar and deltas. Only after that atomic write and directory synchronization succeed is the payment charged. The charge is made in memory at once, and the player's save writes it: it lands, or, when the purse cannot cover it, is refused and changes nothing. A charge that landed is recorded by a durably written paid marker before the description is sent, and a delivered marker is written after sending it; a refused one is recorded as failed. All receipt reads and writes run in workers; the game pulse only polls ready futures. A storage failure prevents charging or delays delivery, depending on which boundary failed.

Login, reconnect and copyover recovery resume a prepared receipt and show a paid receipt that was never delivered. They print nothing for delivered or failed receipts. Players can also use `stat receipt` at the lockers to recover or reread the latest receipt, including when automatic recovery was busy or ordinary network output was lost. A prepared receipt is charged on recovery: the server that wrote it stopped before recording a charge. Memory is the authority, so the charge that server made in memory is normally lost with it. Only when the player's save landed in the moment between the charge and the paid marker, and the server then stopped, is the purchase charged twice. Account and racewar must still match before recovery submits payment or displays text.

The latest receipt is retained after delivery, so `stat receipt` can repeat its text without charging. Automatic recovery does not repeat it. If the delivered marker is not saved, for example after a crash right after the text is sent, the next login, reconnect or copyover shows the text once more. A later identification replaces the previous paid, delivered or definitively failed receipt. An unresolved prepared receipt is recovered before another selection can be accepted. This is one recoverable latest purchase per player, not a historical archive or a guarantee of exactly-once network output. Older builds reject the delivered state as an invalid receipt, which blocks paid identification for that player; do not roll back to a binary that cannot read delivered receipts.

## Storage and operational bounds

An explicit `stat receipt` joins a pending recovery for that player instead of
being dropped. A reread requested while the delivered marker is being written is
shown after that worker finishes. These requests reuse the existing admission
slot and never submit another payment for a finished receipt. When all slots are
occupied by other players, `stat receipt` reports that the clerk is busy.

Receipts live under `CRITICAL_COMMAND_JOURNAL_DIR/locker-identification/<pid>.receipt` on both backends. The directory is private (0700), files are private (0600), and an exclusive service lock prevents two processes from operating the same receipt store. Files contain a bounded binary command, at most 64 KiB of captured text, and a SHA-256 checksum. Reads reject wrong player IDs, corrupt/truncated data, oversized data, public permissions, symlinks and nonregular files. Initialization failure disables the paid service.

At most 16 requests, each with at most one worker operation, are active at once. Busy explicit callers can retry. Automatic login, reconnect and copyover recovery that finds all slots occupied retains one deferred entry per player ID, then starts when a slot opens. Repeated automatic notifications are deduplicated. Deferred entries contain no character pointers, receipt text or worker futures; each is resolved against the current playing character before admission, and disconnected players are skipped. Each pulse examines at most 16 deferred entries, including disconnected-player cleanup. Shutdown clears deferred notifications; the next login or copyover rediscovers the durable receipt. Failed writes retry at one-second intervals while the owner is online. Disk latency does not block the game pulse; orderly shutdown joins outstanding I/O and therefore can wait for storage. A process crash leaves the last durable prepared or paid state recoverable.

Keep the receipt subdirectory in recursive backups of `CRITICAL_COMMAND_JOURNAL_DIR` (named for the critical-command journal it held before the persistence reset), alongside the player data. Do not selectively delete prepared receipts. The lifecycle manifest classifies these files under `file:critical_command_journal`. New code cannot reconstruct descriptions lost by the older process-local implementation before this upgrade.

## Validation

`python3 tests/async/test_locker_receipt_recovery.py` runs the production receipt service and codec with controlled scheduling and networking. It charges an in-memory purse the way the live service does and saves it after the completion, as the player's next save would. It exits separate processes before the charge, after the charge (before the save), and after the paid marker, then recovers wallet and bank purchases and verifies one debit and the original text. A further process verifies that automatic recovery of the delivered receipt prints nothing and submits nothing, while `stat receipt` still shows the original text. It also checks duplicate callbacks, disconnect recovery, ownership, admission, insufficient funds, storage failures, malformed receipts, and `stat receipt` during pending recovery, a pending delivered-marker write and full admission. A blocked storage worker leaves 10,000 game pulses responsive without submitting payment.

Every crash boundary also runs with 40 online players without receipts queued before the recovering player, reproducing copyover admission before the first pulse. These cases verify that prepared and paid recovery survives multiple admission batches, charges once and preserves silent automatic handling of delivered receipts. The harness also checks repeated automatic notifications, disconnected deferred players, explicit rereads claiming deferred entries, shutdown cleanup and the 16-active-request limit.

`test_locker_identify.py` checks the actual lore renderer for weapons, armor, totems, potions and wands. `test_currency_in_memory.py` applies a prepared payment the way the receipt service submits it; `test_currency_transaction_contract.py` retains schema and source contracts. These controlled tests do not constitute a live multiplayer latency benchmark.

## Backup and restore qualification

The backup preserves `locker-identification/<pid>.receipt` and its empty
`.service-lock` under `journal_roots.critical`. Receipt filenames must
contain a positive signed 32-bit player ID and files must fit the native codec's
size bound. Existing ownership, permissions, symlink, hardlink and capture
consistency checks still apply. Transient or unexpected files fail capture.

The restore verifier (`qualify_flatfile_restore --receipts`) checks this directory
before service boot. It accepts only an empty service lock and receipts that pass the
production bounded decoder, including checksum, payment validity and matching player
ID. Receipts remain available for the player to claim after recovery on either
persistence backend.
