# Player Save Journal (retired)

Player saves are no longer journaled. They go straight to the one persistence writer
(see [Player Save Pipeline](PLAYER_SAVE_PIPELINE.md)); a queued save lives only in
memory, and a crash loses at most the last 30-second checkpoint.

Servers before the persistence reset kept a journal in `PLAYER_SAVE_JOURNAL_DIR`. If
that variable is still set, boot replays a leftover journal once through the normal
save path, before the writer starts:

- Records are ordered by PID and revision; exact duplicates are skipped.
- A record the database already holds, or holds a newer revision of, is skipped.
- Anything that cannot be applied stays in the file, and the file is renamed
  `player-save.journal.retired-<milliseconds>`. It is never replayed again, because
  a later replay would roll the character back over newer saves. An alert names how
  many records were left.

`world persistence` reports `legacy_journal_replayed` and `legacy_journal_retired`.
Keep retired files: each may hold the only copy of a save that failed before the
reset. Never copy journal, retired or quarantine files into commits, tickets or logs.

The journal format and its safety rules (mode `0700` directory, `0600` files, CRC32
framing, quarantine of corrupt records) are unchanged; the reader lives in
`src/player/player_save_journal.c` until the code is removed in Phase 3 of the
[persistence reset](../ongoing-projects/2026-09-28-persistence-memory-authority-plan.md).
