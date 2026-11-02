# Locker shutdown recovery

Ordinary shutdown/reboot must exit even when a locker cannot prepare a save.
An empty persistence-writer queue does **not** prove that its live items reached
storage. Departure can refuse before creating a dirty slot, and capture or queue
admission can fail afterwards.

## What is preserved

After input has stopped, command drains and terminal character saves have been
attempted, shutdown captures every occupied locker and retained terminal locker
holder. This traversal does not move items or call departure, `LockerToPFile`,
private durability, purchase, or audit completion code. It captures:

- public chest contents, loose non-corpse room items, and holder inventory;
- each private chest's contents under its existing locker/chest IDs;
- equipment and inventory of PCs still occupying those rooms. This preserves
  items taken from a chest even when its durability barrier refused the player's
  terminal save. Player status, wallet, bank, purchase state and other components
  are excluded.

The image uses the existing item/player snapshot codecs, a versioned envelope
and SHA-256 integrity check. Its directory/file permissions are 0700/0600. It is
bound to the configured backend and database connection settings (or flat-file
root). It contains private player/item data: restrict access and include it in
the same backup and retention policy as player persistence.

Publication runs in a child that uses only filesystem syscalls and never touches
the database or inherited C++ services. A file is written and synced as
`shutdown.pending`, renamed to `shutdown.image`, and its directory synced. The
parent waits only until the **existing writer deadline**, then kills the child
without joining blocked disk I/O. Image capture/publication does not grant the
writer a fresh 30 seconds. Copyover continues to use its existing cancellable
drains; pwipe does not create a shutdown image.

## Restart

The recovery directory is relative to the game's data directory:

- MariaDB: `runtime/locker-shutdown/`.
- Flat-file: `$FLATFILE_STATE_DIR/locker-shutdown/` (native private chests remain
  unavailable on that backend).

Boot locks the directory and checks recovery **before artifact population
reconciliation, unheld-item reaping, world loading, or player admission**. A
complete image is decoded in full, then applied through the existing locker,
private chest and item-only player repositories. These make item ownership agree
with the captured memory, retain nesting, and filter destroyed items using the
normal save rules. Existing purchase receipts and metadata are preserved.

Only after every replacement commits does boot durably remove the image. A
database failure or a crash partway through replay leaves it available for the
next boot. Reapplying the same owner snapshots before admitting gameplay is safe;
no additive payments or item grants are replayed.

## Reporting and intervention

The console/stderr and file log report:

- `RECOVERABLE locker shutdown: image_published=1 capture_complete=1`: a complete
  image was durably published; the next boot still must apply it successfully.
- `UNRECOVERED locker shutdown`: capture/publication was incomplete, failed, or
  exceeded the deadline. This is an operational failure, even with an empty
  writer queue. Check the console as well as the file log if logging/storage is
  impaired.
- `Locker shutdown recovery applied: chests=... players=...`: all captured owners
  were applied and the image removed.

Per-locker capture logs identify pending item-movement, chest-write, purchase and
audit barriers. The image recovers items; it does **not** certify completion of
these operations. Inspect the ordinary `not_written` reports and purchase/audit
records separately. An unfinished detached creation grant is still governed by
its existing committed transfer payload; this image does not issue a second grant.

A missing holder, wrapper, chest object, malformed item graph, allocation/size
failure, or duplicate UID can make a complete recovery impossible. Available
partial captures are retained as an incomplete image when they can be encoded.
Already missing live data cannot be reconstructed from a queue drain. A failed
disk write may leave no image at all; its `UNRECOVERED` console record is the
evidence, and the last database/backup state must be reviewed explicitly.

When boot reports `Locker shutdown recovery unresolved`:

1. Keep player admission stopped. Preserve the entire directory, console/file
   reports and a consistent database/flat-file backup before changing anything.
2. If storage or database access failed, repair access and restart with the same
   backend, database and data directory. A valid image whose apply failed will
   retry automatically. Do not copy the image to another database or clear it to
   get the server online.
3. A `shutdown.pending` file, corrupt/incomplete image, wrong-store image, or
   missing source requires owner/staff reconciliation. Retain the original;
   compare its captured UID graphs with durable payloads, current ownership,
   transaction receipts/audit and backups. Restore each item to one owner, with
   its quantity and contents, before an owner-approved removal of the blocking
   evidence. Do not blindly promote a pending file or import a partial image as
   an empty replacement for unknown contents.

This is orderly shutdown recovery, not a periodic crash journal. A power loss
before publication, unavailable storage, or data already missing from memory
can still require backup/manual recovery. Deployment and production data changes
remain subject to the repository's owner-permission rules.

## Focused proof

`python3 tests/async/test_locker_shutdown_recovery.py` uses separate processes and
a disposable socket-only MariaDB. It exercises production departure guards,
read-only locker traversal, item/player capture and codecs, child publication,
boot replay and ownership repositories. Fault boundaries are controlled; no live
server faults or production data are used. The shutdown/copyover wiring and shared
deadline are also checked by `test_shutdown_writer_bound.py`.
