# Character deletion outcomes

`delete_character()` (`src/core/files.c`) deletes a character's stored state and then lets
memory forget it. It never consumes the character, and it reports the outcome to its
callback on the game thread: at once on flat-file, on a later pulse on MariaDB, where the
deletion is one writer job. The character may leave the game before the callback runs
(hardcore death, `terminate`), so what memory must forget is captured when the deletion
starts.

- `deleted`: the backend confirmed the deletion. Only then are the successful-deletion
  audit events and success message emitted.
- `refused`: validation or backend cleanup failed. On MariaDB the job's transaction rolls
  back (a commit whose outcome is unknown is reported by the writer, not retried); the
  character, its account mapping and everything memory holds of it remain, so a fresh load
  and a retry work. Flat-file failures retain the authority coordinator's journal and
  recovery contract.
- `reconciliation_required`: the deletion committed but the zone-story state could not be
  cleared. The menu asks the player to contact an immortal before retrying.

## Transaction and runtime boundaries

On MariaDB the job runs, in one transaction on the writer's connection and behind every
save queued before it: the account-character and frag-leaderboard tombstones, visitor
locker access removal, artifact release (repeated in `artifact_domain_state`), the guild
saved without this member, personal locker deletion (when requested), ship row deletion
and player-row deletion. The guild's statements are built while its live member links and
frag counters are staged without the member, then restored at once.

After the commit, memory lets go of the character (`forget_deleted_character()`): its
revision state, name-index entry and artifacts, its guild membership (without
`Guild::kick()`, which changes departure penalties and writes the character), its entry
in every live session's account list (names are unique, so only its account lists it),
its ship and stored ship rows, and its zone-story state. The account list removal skips
the account save: the deletion's tombstone already records it.

The account menu waits for the reply with its input held (`wait_for_writer()`); a
connection closed meanwhile drops the reply, and the deletion still completes. The
websocket deletions load the character through the player load pipeline and delete it
the same way.

The flat-file coordinator retains its atomic authority operation, then the same memory
release.

Confirmation loads exclude items and pets. Success, failure, cancellation and replacement
selection all detach both descriptor/character references and free the temporary
character. The negotiated terminal type is preserved.

## Verification

`python3 tests/async/test_account_character_delete_runtime.py` compiles the production
menu, `delete_character()`, the memory release, account-list removal and the guild
staging against test doubles under ASan and UBSan, once per backend. On MariaDB it holds
the queued job, fails it at each of its statements (nothing is forgotten, the session is
told and released), retries successfully, and closes a session before the reply. It also
covers flat-file failure and success, repeated confirmation, cancellation, replacement
selection and list removal at either end.

`tests/async/run_mysql_deletion_journey.py` (in `make test-db`) deletes a real character
on a disposable MariaDB: triggers refuse the tombstone and the player-row deletion (the
mapping and inventory stay, the character reconnects and plays), the retry deletes it
once, and a restart does not bring it back.

The flat-file character-deletion harness separately exercises the real journal and
repository coordinator.

## Protected operator follow-up for issue 200

The historical disposable identity was deliberately omitted from the public
issue. This checkout has no `.env` or protected evidence identifying that player.
No production database query or player-data mutation was performed for this fix.
The historical check remains pending and must not be inferred from a likely name.

An operator should recover the exact account/PID from the original protected
September 5 investigation, verify that the evidence identifies an authorized
disposable test character, and inspect its current player row, account mapping,
and relevant cleanup domains read-only. Keep those identifiers and query results
out of public issues and pull requests. If absent, record that result privately.
If present, obtain or confirm cleanup authorization for that exact identity and
reconcile its current state before deleting it. Legacy partial cleanup and
unacknowledged commits require this evidence-based review; the new transaction
boundary does not retroactively repair old partial deletions.
