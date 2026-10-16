# Unread news in player prompts

Status: implementation and local acceptance are complete. Both PRs are open and
ready for review: [#127](https://github.com/LuminariMUD/Duris/pull/127) (publication)
and [#128](https://github.com/LuminariMUD/Duris/pull/128) (acknowledgement and prompt).
No merge or deployment was performed.

Inspected 2026-10-16 against Duris master
`277df52d82e5cfccc5689013c3310141a02aea43`, after fetching origin and verifying that
the workspace HEAD matched the remote master. Planning branch:
`branch/news-publication` (first chunk) and `branch/unread-news-prompt` (dependent
feature chunk).

Reference: Luminari-Source at
`56fca2e452ce0c4186f827812ea8334d6546fb4e`. Its
[prompt](https://github.com/LuminariMUD/Luminari-Source/blob/56fca2e452ce0c4186f827812ea8334d6546fb4e/src/core/comm.c) compares `GET_LAST_NEWS` with
`newsmod`; [the news command](https://github.com/LuminariMUD/Luminari-Source/blob/56fca2e452ce0c4186f827812ea8334d6546fb4e/src/act/act.informative.c)
sets the character's last-read time when opening news.
[Player saves](https://github.com/LuminariMUD/Luminari-Source/blob/56fca2e452ce0c4186f827812ea8334d6546fb4e/src/player/players.c) persist that value,
and [file loading](https://github.com/LuminariMUD/Luminari-Source/blob/56fca2e452ce0c4186f827812ea8334d6546fb4e/src/core/db.c) and
[text editing](https://github.com/LuminariMUD/Luminari-Source/blob/56fca2e452ce0c4186f827812ea8334d6546fb4e/src/olc/tedit.c) update `newsmod`.

## Outcome and behavior

Add the literal marker `(news)` to a player's ordinary game prompt while the
current published news has not been acknowledged by that character. Opening
`news` clears it; publishing different news makes it appear again.

The implementation must satisfy these acceptance criteria:

1. **Unread and read:** a character with no acknowledgement sees `(news)` when
   nonempty news is available. Successful `news` output acknowledges exactly the
   content opened. The next ordinary prompt omits the marker. Opening the pager
   counts as reading; reaching its last page is not required.
2. **Independent characters:** acknowledgement belongs to the character, matching
   Luminari. Reading on one character does not dismiss another character's marker,
   including two characters on the same account.
3. **Changed content:** different published bytes make the marker return for
   online and subsequently logged-in characters. Re-reading unchanged content,
   reimporting it, reloading it, or rebooting does not create a new notification.
   Color, whitespace, and typo edits count as changes. Reverting to content that
   equals a character's last acknowledged content needs no acknowledgement again.
4. **Persistence:** the acknowledged content survives a completed save, rapid
   logout/login, clean restart, and copyover, in both MariaDB/MySQL and flat-file
   modes. Older saves and existing database rows default to unread. An abrupt
   crash before the normal asynchronous save completes may show the reminder
   again; this feature does not introduce stronger durability than player saves.
5. **Failed opening or save admission:** paging-disabled refusal, absent usable
   news, no live recipient, or command-output capacity refusal must not mark news
   read. If the status save cannot be admitted, retain the old acknowledgement
   and give a brief retry message after displaying news. A later worker failure
   follows the existing dirty/retry and persistence-reporting paths.
6. **Prompt coverage:** render the marker once in normal and two-line prompts and
   in the smart-prompt branch. Preserve existing prompt-off, old-smart-prompt
   suppression, death, transaction deferral, login, confirmation, editor, and pager
   behavior. Do not insert it into a pager's navigation prompt.
7. **Correct owner:** switched staff and morphed players use the owning PC's
   acknowledgement. Ordinary NPCs and missing descriptors never access PC data.
8. **Consistent publication:** the text and its fingerprint change together on
   the game thread. A refresh during an already-open pager cannot acknowledge the
   new text; the pager retains its existing copy, and new news remains unread.
9. **No prompt I/O:** prompt rendering only compares cached values. No hashing,
   database access, file reads, save requests, or background work per prompt.

The existing login notice remains a notice; displaying it does not acknowledge
news. With no published news, show no marker and make `news` explain that news is
unavailable without recording a read.

### Non-goals

Account-wide acknowledgement, MOTD or mail markers, unread entry counts, news
history, a new notification framework, per-marker configuration, client UI or
GMCP protocol additions, filesystem watchers, and changes to news authoring are
outside this feature. Existing whole-prompt settings remain authoritative.

## Inspected baseline and consequences

- [News loading](../../src/world/db.c) assigns the global `news` string from
  `get_mud_info("news")` at boot. [Staff `page`](../../src/cmd/actcomm.c) reloads
  news/MOTD/wizMOTD. Its `page info` and `page help` branches are separate and must
  remain separate.
- [SQL mud-info publication](../../src/sql/sql.c), `mud_info_publish`, updates a
  map at boot, on staff reload, and through the
  [one-minute refresh](../../src/net/comm.c). The periodic path currently does
  **not** update the separate global `news` string used by `do_news`. Fix this
  specific disconnect as part of publishing news and its fingerprint together.
- The client-free SQL branch reads tracked information through
  [flatfile_information_read](../../src/flatfile/flatfile_help_catalog.c).
  `sql_mud_info_refresh` is a no-op there. Flat-file publication therefore remains
  boot or staff `page`; editing the source file alone is not publication into the
  running server. Preserve its allow-list and bounded file reader.
- [`do_news`](../../src/cmd/actinf.c) requires `PLR_PAGING_ON`, then calls
  `send_to_char` with `LOG_NONE` for the body. It records no read state.
  [Automatic command paging](../../src/net/comm.c), `process_with_paging` and
  `send_to_char`, buffers command output; [page_string_real](../../src/net/modify.c)
  duplicates it for the pager. The output buffer can refuse an oversized body,
  so calling a void output function alone is not proof that news was accepted.
- [`make_prompt`](../../src/net/prompt.c) has early returns for pager, editor,
  connection/confirmation, smart prompt, and a zero prompt mask. The final prompt
  append uses `pPrompt` and its remaining capacity. Cover the smart branch as well
  as this final append; retain color resets and MSP framing.
- [`GET_PLYR`](../../src/core/utils.h) already resolves morph/switched ownership.
  [Output preferences](../../src/player/output_preferences.c) demonstrate guarded
  PC resolution and status-save admission with restoration on queue failure.
- Character state travels through [capture](../../src/player/player_snapshot_capture.c),
  [snapshot/codec](../../src/player/player_snapshot.h),
  [SQL write](../../src/player/player_snapshot_repository.c),
  [SQL read](../../src/player/player_load_repository.c), and
  [materialization](../../src/player/player_load_materialize.c).
  [Flat-file merging](../../src/flatfile/flatfile_player_repository.c) replaces
  `status_strings` only when `PLAYER_COMPONENT_STATUS` is included. Reuse that
  vector rather than adding a second persistence path.
- Snapshot schema is currently 8; the decoder also accepts 1, 3, 5, and 7.
  Materialization requires exactly seven status strings and validates their IDs.
  Adding an eighth string without upgrading old snapshots would refuse logins.
- The authoritative migration head is **0042_player_base_stats**, in the
  [manifest](../../migrations/migration_manifest.json) and
  [compiled contract](../../src/core/runtime_compatibility_contract.h).
  Some explanatory documents still mention 0041; use the manifests and actual
  schema measurements when preparing the next migration.

## Minimal implementation

### 1. Publish one current news value

Add a small `src/player/news.c` and `src/player/news.h` shared by publication,
`do_news`, and prompt rendering. It owns the current text and content fingerprint;
replace the old writable `news` global and direct assignments rather than keeping
two authoritative copies. Expose only the operations these callers require.

Use SHA-256 from the already-linked crypto library, represented as 64 lowercase
hex characters. Hash the exact loaded source bytes, before recipient rendering,
only when publishing changed content. Empty means no news; an empty saved
fingerprint means never acknowledged. Do not use file mtime, a news-heading date,
`std::hash`, an uptime counter, or a wall-clock read timestamp.

Build the candidate text and fingerprint before replacing the current pair. SQL
boot, successful `mud_info_publish`, and explicit staff reload all use that
publication operation; successful periodic SQL refresh therefore updates both
what `news` shows and what prompts compare. Keep the existing asynchronous SQL
read and interval, with no second poller or per-player invalidation sweep.

For flat-file mode, use the existing bounded information reader at boot and staff
reload. Distinguish a failed read from a successfully read empty file instead of
turning every failure into a new version. A failed query/read or invalid candidate
retains the last good published pair and reports through the existing diagnostics.
At boot with no good value, news is unavailable. A successful SQL read with no news
row, or a successfully read empty file, publishes no news. Neither case changes
characters' saved acknowledgements. A missing flat file is a read failure, so an
already-running server retains its last good copy.

After publication, the marker changes on each player's **next otherwise eligible
prompt**. Do not force unsolicited prompts into editors, paging, or idle output.

### 2. Save acknowledgement with character status

Add `last_read_news_hash` as a zero-initialized, fixed-size `char[65]` in
[`pc_only_data`](../../src/core/structs.h). This structure has C-style allocation
and clearing sites; do not add a nontrivial string member to it.

Append `last_read_news_hash` to `player_status_string_field`, preserving all
existing numeric IDs. Capture it with `PLAYER_COMPONENT_STATUS`. Add its SQL
column mapping, bounded load, and materialization; update the exact string count
and field validation together. The allowed value is empty or 64 lowercase hex
characters. Malformed acknowledgement text becomes unread, with a diagnostic,
rather than preventing login; keep structural snapshot-corruption checks intact.

Advance the snapshot wire version from 8 to the next free version at implementation
time. Continue accepting all currently supported versions, including 8, and
upgrade their status payloads with exactly one empty acknowledgement entry.
Preserve existing legacy upgrades such as the learned-flight-stop default. Do not
add status rows to snapshots that omit status, and reject duplicate IDs and new
field IDs smuggled into an old wire version. Verify the normal capture size budget
includes the additional row and value.

The existing flat-file status merge already carries the string vector. Prove
status updates replace the acknowledgement and item-only or other component saves
retain it; no extra player sidecar file or flat-file merge member is needed.

Add one guarded immutable migration for
`player_data.last_read_news_hash VARBINARY(64) NOT NULL DEFAULT ''`. Existing
characters receive the empty default without a backfill of invented read times.
The verifier must check type, byte capacity, nullability, and default, and refuse
an incompatible pre-existing shape without losing rows.

Register the next available migration (0043 is next at this baseline, but do not
reserve it across other work). Update apply/verifier checksums, history/head,
measured MySQL and MariaDB metadata fingerprints, the runtime manifest and compiled
header together. Do not edit a prior immutable migration or rewrite the sealed
bootstrap to replace an upgrade. This adds a column, not a table: table inventory
and lifecycle ownership remain unchanged. Update persistence documentation for
the new field and format; use the existing player-data export/erasure paths.

### 3. Acknowledge the content actually opened

Resolve and validate the recipient's owning PC before touching acknowledgement
state. Keep output addressed to the active descriptor/body so the real command
pager still receives it. Preserve the existing paging-enabled requirement and
test the actual dispatch/body flags for switched and morphed characters; resolving
the owner alone does not establish that output will be paged.

Capture the current text/fingerprint pair for the command. Check availability
and that the complete header/body can enter the existing command-output buffer;
reuse its capacity information rather than duplicating its numeric limit. Make
any required output-capacity accessor narrow and reusable by this actual caller.
An oversized or otherwise rejected body must leave the marker visible and give
an explicit message. Keep authored news colors and `LOG_NONE`; do not change the
pager architecture or clear the marker for only an error/header.

After the body is accepted into command output, install the captured fingerprint
on the owner and request `PLAYER_COMPONENT_STATUS` through
`player_save_pipeline_request`, using the owner's normal save intent and room.
Reuse the output-preference pattern: keep the new value for `queued`/`coalesced`,
restore the old value on admission failure, and avoid a write when it is already
equal. Do not issue a direct SQL update, block for a disk write, or add a private
retry queue. Existing terminal saves and queued-load holds provide clean
logout/copyover and rapid-relog ordering.

The acknowledgement means the command accepted that news for display, not that
the human finished reading or that a network client confirmed delivery. Quitting
the pager does not undo it. Publishing version B while the pager shows version A
leaves the acknowledgement at A until another `news` command opens B.

### 4. Render the marker without changing prompt policy

Use the same validated owner for the read check in `make_prompt`. Add one bounded
`(news)` append alongside the existing prompt extras; include it once on the final
line of a two-line prompt and before the smart branch's terminator. Reserve room
for terminators, resets, and MSP closing markup. Follow current prompt coloring
and preserve the literal visible text for plain clients.

No new prompt bit is needed. A zero ordinary-prompt mask stays silent; the smart
prompt still follows its existing branch. Preserve transaction deferral and other
suppression in `process_output`. Telnet and WebSocket text should carry the same
marker through their existing output routes, without new protocol messages.

## Files and implementation order

- [x] Add the small news owner/publication module; connect boot, SQL publication,
  and staff reload in `world/db.c`, `world/db.h`, `sql/sql.c`, and `cmd/actcomm.c`.
  Register the source in [src/Makefile](../../src/Makefile), whose server object
  list is explicit, for both maintained backend builds.
- [x] Add the PC field, appended snapshot string ID, capture/codec upgrade,
  SQL mappings, and materialization in the existing files cited above. Update
  old-version fixtures and strict field-count fixtures together.
- [x] Add the immutable migration/verifier and synchronized runtime contracts;
  measure schemas on disposable databases before compiling the final binary.
- [x] Wire `do_news`, the minimum command-output capacity check in `net/comm.c`
  and its header if needed, and both relevant prompt branches. Queue the status
  save only on a newly acknowledged version.
- [x] Extend focused production-linked tests and run the journeys below. Update
  the existing news help entry where it is maintained and the relevant
  persistence/prompt documentation; do not announce implementation before it lands.

## Proof required before implementation is complete

These are the implementation acceptance gates; completed results and exact
journey commands are recorded in the handoff below. Reuse existing test runners and production functions; source-string
assertions alone do not prove behavior.

1. **Publication and command:** extend
   [the real output/pager harness](../../tests/async/test_word_output_integration.py)
   to execute production `do_news` and `make_prompt`, with the actual news module.
   Prove A unread -> open A -> read; unchanged reload remains read; B returns the
   marker; same-account second character remains unread. Test empty/unavailable
   news, failed reload preserving A, paging off, output refusal, no descriptor,
   NPCs, switched/morphed ownership, and a rejected save submission. Test A in an
   open pager while B publishes. Include current-size news and the exact command
   output boundary, including its header. Preserve
   [the login notice regression](../../tests/async/test_account_login_news.py),
   updating its old global-string assertion to the actual new output path.
   Exercise the real SQL refresh/staff-reload completion paths with controlled
   returned rows and failures, plus flat-file boot/reload reads. Calling only the
   new publication helper cannot prove the existing cache/text disconnect is fixed.
2. **Prompt output:** extend
   [combat_prompt_checks.inc](../../tests/async/combat_prompt_checks.inc) and
   [the transport/prompt harness](../../tests/async/test_item_movement_prompt_runtime.py).
   Cover normal/two-line/smart, prompt off, old-smart suppression, combat, colors,
   MSP, Telnet GA, WebSocket text, pager/editor/confirmation, and deferred output.
   Assert one marker and intact closing/reset bytes; retain existing no-news
   fixtures so unrelated prompt expectations stay meaningful.
3. **Persistence and compatibility:** extend the capture, codec, SQL repository,
   materialization, and flat-file harnesses. Verify valid and malformed hash
   handling, round trips, all supported old wire versions, duplicate/unknown IDs,
   status-only saves, unrelated component saves, and a rapid reload held behind
   an outstanding save. Use actual materialization, not just DTO equality. Extend
   existing player-save admission/failure checks only where acknowledgement adds
   a new assertion; reuse the established worker retry behavior.
4. **Migration:** on disposable MySQL 8.0 and MariaDB 10.11 schemas, prove fresh
   baseline-to-head and populated previous-head-to-new-head upgrades, a second
   application with no data loss, empty defaults for existing rows, and verifier
   rejection of an incompatible pre-existing column. Run the actual immutable
   runner and verifiers; a hand-applied ALTER is insufficient. Derive both runtime
   metadata fingerprints from the resulting clean schemas, never production.
5. **Player journey:** in each backend, log in with a test PC, observe `(news)`,
   type `news`, leave the pager, observe its removal, then logout/reconnect and
   clean restart/copyover without it returning. Publish B using that backend's
   normal path, observe `(news)` again on the next prompt, read B, and verify the
   persisted acknowledgement. Include a second PC and verify that the login
   notice does not dismiss the marker. Read only environment mode before local
   operations; use the configured test account without printing credentials.

Existing entry points to extend/run individually as applicable:

```sh
python3 tests/async/test_account_login_news.py
python3 tests/async/test_word_output_integration.py
python3 tests/async/test_item_movement_prompt_runtime.py
python3 tests/async/test_gmcp_prompt_regressions.py
python3 tests/async/test_flatfile_help_catalog.py
python3 tests/async/test_player_snapshot_capture.py
python3 tests/async/test_player_item_snapshot_codec.py
python3 tests/async/test_player_load_topology.py
python3 tests/async/test_player_save_pipeline.py
python3 tests/async/test_flatfile_player_repository.py
bash tests/async/run_player_load_repository_mysql.sh
bash tests/async/run_output_preferences_mysql.sh
python3 tests/async/test_immutable_migration_runner.py
RUNTIME_DB_IMAGE=mysql:8.0 bash tests/async/run_runtime_compatibility_mysql.sh
RUNTIME_DB_IMAGE=mariadb:10.11 bash tests/async/run_runtime_compatibility_mysql.sh
python3 scripts/validate_runtime_compatibility.py
./scripts/format.sh --check
make -C src
git diff --check
```

Also compile the flat-file backend in a separate `bin/` output location using
the maintained [build instructions](../guides/BUILDING.md). Record exact commands
and results with the implementation. Run any newly needed news-specific journey
directly and report its name then; the list above is not a claim that those
existing tests already cover this feature. No CI wait replaces local evidence.
The existing output-preferences database harness already connects the real status
writer and reader; extend it with the acknowledgement round trip rather than
claiming the read-only player-load harness proves persistence.

## Ablation and delivery boundary

Keep a content fingerprint, one saved character field, the shared publication
boundary, and tests of the real command/prompt/save paths: each is required by an
acceptance criterion. Reuse `status_strings`, the existing writer, and the existing
refresh workflow. Drop timestamps, per-account state, a version table, reset
sweeps, a private save queue, a new poller, extra prompt toggles, and a generic
notification system. No requirement depends on them.

Publish two focused, dependent PRs as they are ready: (1) consistent cached news
publication and reload, with its regression tests; (2) persisted acknowledgement,
migration, command/prompt integration, and the full player journeys. The second
PR will target the first until it lands. Before landing either, recheck current
master, migration numbering, and the complete tested tree. For deployment, apply
the additive migration before booting the new database-backed binary; the existing
runtime gate should refuse an old schema. Preserve the previous binary and normal
recovery backups, and document that an old decoder cannot read newly written
snapshot versions. Production migration/restart requires the owner's deployment
authorization and is outside this planning task.

### Planning verification

The plan was checked against the source paths above after refreshing master.
Master advanced from `448ca4bcb` to `277df52d8` during the review; the workspace was
fast-forwarded and the overlapping `actinf.c`/`comm.c` changes were inspected.
Those changes concern epic-task refresh and do not alter the traced news paths.
The review explicitly covered cache/text divergence, command-output rejection,
save-admission failure, raw PC allocation, strict snapshot counts and legacy
upgrades, migration-head drift, prompt suppression, and morph/switched ownership.
At the planning checkpoint, only documentation links, commands, and whitespace
were checked. Runtime acceptance was performed during implementation, as recorded
below; planning checks were never treated as feature proof.

### Implementation handoff - 2026-10-16

- Latest master re-fetched at implementation start: `277df52d8`, no divergence.
  Environment mode is local. Existing plan was the only untracked file.
- Ablation retained one cached content/fingerprint pair and the existing status
  writer. The `status_strings` vector avoids a separate flat-file member or store.
  Two chunks allow the independently useful stale-news refresh fix to be reviewed
  before persistence and UI work completes. No tags or deployment are needed.
- Shared publication and boot/reload wiring are implemented. The SQL mud-info
  cache now delegates its news value to the same published pair as `do_news`.
  Native and flat-file publication regression tests pass, including unchanged
  bytes, embedded-NUL rejection, failed reads, empty content, and real SQL refresh
  and staff-reload callbacks. Login notice, flat-file help, information-cache, and
  boot-log regressions pass. `make -C src -j8` passes (full native MariaDB build),
  along with changed-file formatting and `git diff --check`. Build output is in
  ignored `bin/analysis/news/build-publication.log`; focused test output was checked
  directly. `test_news_publication.py` compiles the real SQL reload functions under
  each backend and calls their completion callbacks; it does not contact a database.
- Chunk 1 is published for review as [PR #127](https://github.com/LuminariMUD/Duris/pull/127),
  head `1041fd390`, base master. Local and remote heads matched with `0 0` parity
  and a clean tree before starting the second branch.
- Chunk 2 is complete locally: snapshot schema 9 with an appended status string,
  migration `0043_news_acknowledgement`, saved acknowledgement through the existing
  writer, and prompt/command integration. `send_paged_text` verifies actual
  acceptance of the entire preserved message and rejects an existing overflow
  warning, rather than trusting a void send or only a capacity estimate.
- Final ablation retained the shared news module and normal status vector/writer;
  no extra table, account state, polling service, notification framework, or save
  queue was added. The prototype capacity accessor was replaced by a single
  acceptance-returning send used by the command.
- Validation found and repaired two prompt-tail defects: a long NPC name followed
  by unchecked condition text could overflow the buffer (reproduced as a fortified
  buffer-overflow abort), and two-line mode without resource fields could send an
  uninitialized second buffer. Bounded tail appends now reserve the marker and
  closing frame; only a constructed second line is sent. Sanitized tests cover
  the long name, closing MSP tag, and the resource-free two-line modes.
- The existing schema-measurement helper had stale hard-coded table counts (186
  bootstrap / 203 runtime). It now takes the bootstrap count from the checked-in
  CREATE TABLE declarations and the runtime count from the checked-in manifest.
  Both complete schema measurements and drift matrices pass; no schema check was
  disabled. The actual current counts are 183 bootstrap and 198 runtime tables.
- Native and flat-file builds pass. The real SQL writer/reader and flat-file
  repository tests prove independent character defaults, saved hashes, reconnect,
  failure rollback, and unrelated component preservation. Capture tests execute
  production capture; the output harness executes production `apply_string` for
  valid/empty/malformed hashes. Codec tests cover versions 1/3/5/7/8, partial saves,
  version-9 round trips, duplicate IDs, and old-version ID smuggling.
- The production-linked output/pager harness passes under ASan/UBSan. It covers
  successful opening, repeat reads without another save, paging refusal, empty
  content, output boundary/refusal, save admission errors, a refresh while the
  pager is open, normal/two-line/smart/off prompts, editor/confirmation, and NPC,
  switched and morphed ownership. The transport harness passes unread markers
  through real ANSI/Telnet/WebSocket output and proves old-smart suppression,
  transaction deferral, death suppression, and no duplicate prompts.
- The two-engine immutable migration runner tests pass on both fresh databases
  and populated head-0042 databases. They prove failure before recording an
  incompatible existing column, retained player rows, empty defaults, a harmless
  second application, and rejection of length/type/nullability/default drift.
  Both full runtime-compatibility scripts also pass their schema/drift matrices.
- Both full-world journeys pass on disposable authorities and test accounts:
  unread -> read, independent characters, unchanged reload, changed news,
  logout/reconnect, copyover, and clean restart. The MariaDB journey additionally
  proves automatic one-minute SQL refresh. Each reads back the stored hash and
  compares it to the displayed version's SHA-256. The fixture uses the existing
  shortened camp timer; an initial default-camp timeout was a fixture delay, not
  a persistence failure. No checkout account, running server, or production data
  was used. Final journeys were repeated after the prompt-tail repair.

Reproduction commands for the completed additional gates (from repository root):

```sh
SANITIZE=1 python3 tests/async/test_word_output_integration.py
python3 tests/async/test_player_load_pipeline.py
python3 tests/async/test_news_publication.py
python3 tests/async/run_news_migration.py --image mysql:8.0
python3 tests/async/run_news_migration.py --image mariadb:10.11
make -C src -j4
make -C src -j4 PERSISTENCE_BACKEND=flatfile BIN_ROOT="$PWD/bin/analysis/news/flatfile-build"
bash tests/async/with_disposable_mariadb.sh python3 tests/async/run_news_prompt_journey.py --backend mariadb --server bin/server/dms_new
python3 tests/async/run_news_prompt_journey.py --backend flatfile --server bin/analysis/news/flatfile-build/server/dms_new
```

Every existing entry point listed earlier was also run successfully. Local build,
schema, migration, and journey outputs are retained under ignored
`bin/analysis/news/`; the source tests and commands above are the portable proof
recipe. `journey-mariadb.json` and `journey-flatfile.json` record the tested binary
hashes and passed outcomes. No CI result was used as a completion gate.

Review order: #127 targets master; #128 targets `branch/news-publication`. After
#127 lands, refresh master and retarget/rebase #128 as needed, preserving the
reviewed source and rechecking any intervening migration/schema changes. The
feature implementation commit is `351423297`; this final handoff update changes
documentation only. Both branches were pushed and their exact remote heads read
back; no implementation work remains outstanding.

The feature requires migration
0043 before a database-backed deployment, and new schema-9 snapshots require the
new decoder; deployment/rollback decisions belong to the later authorized rollout.
No release tag is appropriate for an unmerged review stack.

### Review repairs - 2026-10-16

Both review findings were reproduced before repair. PR #127's SQL reload called
the success callback after rejecting embedded-NUL news; the flat-file failure
path had the same defect. Both paths now report failure and return without the
success callback, retaining the previous text and fingerprint. The existing
publication harness verifies the failure message, callback suppression, and
retained content for both backends.

PR #128's extra status string shifted the separately materialized wallet, epic,
and frag fields. The loader now records the first integer column after reading
the strings. The existing database fixture uses distinct nonzero values and
neighboring fields, and checks both PID and name loads. The real SQL player
journey also verifies those balances after login, reconnect, copyover, news
acknowledgement, and saving. Both backend journeys check that a refused staff
reload displays no success message and keeps the old news usable.

The review branches were rebased onto master `9625ffd7b`; #128 retains #127 as its
base. The full local gate additionally exposed sibling-checkout source links in
this plan and a stale migration-0042 test expectation. The links now pin the
recorded upstream revision, and the boot test expects migration 0043, matching
the independently verified manifests, compiled contract, and database schemas.
The existing creation/session journeys now expect the unread-news second prompt
line in their unread fixtures; the exact Telnet GA framing assertion is retained.

Focused verification commands added to the reproduction recipe above:

```sh
bash tests/async/run_player_load_repository_mysql.sh
COLOR_DB_IMAGE=mysql:8.0 bash tests/async/run_output_preferences_mysql.sh
COLOR_DB_IMAGE=mariadb:10.11 bash tests/async/run_output_preferences_mysql.sh
RUNTIME_DB_IMAGE=mysql:8.0 bash tests/async/run_runtime_compatibility_mysql.sh
RUNTIME_DB_IMAGE=mariadb:10.11 bash tests/async/run_runtime_compatibility_mysql.sh
python3 tests/async/test_documentation_contract.py
python3 tests/async/test_runtime_boot_compatibility.py
python3 tests/async/test_creation_prompt_journey.py
python3 tests/async/test_game_loop_session_journey.py
```

Validation also includes fresh native/flat-file builds, sanitized output/prompt
checks, both migration replays, both full-world news journeys, formatting, and
`make security-check`. Current review logs are under ignored
`bin/analysis/review/` in the review worktrees; journey reports remain under
`bin/analysis/news/`. CodeQL and Trivy are unavailable locally and were not run.
The PR comments record the full-suite outcome and published heads. The security
summary on #128 advertises a finding but exposes no separate details in its
reviews, inline threads, check runs, or code-scanning alerts; that summary is not
treated as proof that a separate security review passed.

Land #127 first using the repository's linear-history policy, then refresh
master and carry #128's own commits onto that landed parent before retargeting.
No tag, merge, production migration, or deployment is part of this review repair.
