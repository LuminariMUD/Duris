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
`Guild::kick()`, which changes departure penalties and writes the character; the guild is
saved again, so its save lands after any queued while the job ran, which still held the
member), its entry
in every live session's account list (names are unique, so only its account lists it),
its ship and stored ship rows, and its zone-story state. The account list removal skips
the account save: the deletion's tombstone already records it.

The account menu waits for the reply with its input held (`wait_for_writer()`); a
connection closed meanwhile drops the reply, and the deletion still completes. The
websocket deletions load the character through the player load pipeline and delete it
the same way. All three refuse, before anything is queued, a character that is in the game
(linkdead included) or being loaded to enter it: it would play on with nothing saved.
Hardcore death and `terminate` delete the character they extract themselves.

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
covers flat-file failure and success, the refusal of a character in the game or loading,
repeated confirmation, cancellation, replacement selection and list removal at either end.

`tests/async/run_mysql_deletion_journey.py` (in `make test-db`) deletes a real character
on a disposable MariaDB: triggers refuse the tombstone and the player-row deletion (the
mapping and inventory stay, the character reconnects and plays), a linkdead character is
refused, the retry deletes it once, a restart does not bring it back, and the next
character created does not get its pid.

The flat-file character-deletion harness separately exercises the real journal and
repository coordinator.
