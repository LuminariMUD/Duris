# PvP publication privacy: MUD implementation plan

Date: 2026-10-18 UTC. Status: implemented and locally qualified for the
ready-for-review PR. Production rollout and historical redaction remain separate.

This is the MUD-side implementation plan for the
[October 16 end-to-end audit](2026-10-16-pvp-end-to-end-audit.md) and the
[October 18 webinfo privacy investigation](2026-10-18-pvp-webinfo-privacy-investigation.md).
The latter's owner-confirmed whole-POV publication rule supersedes the earlier
equipment-only privacy assurance.

Sources inspected during the initial plan review (before implementation):

- MUD: `fe7f94c42a7b8d22ae289216dbee3af7c723cc6c`; the only pending change is
  this plan. Capture is still payload v3 and has no publication field.
- DurisWeb: `ee9333f5b4d35776d58b404c8e3d02d41d5810b8`, a clean checkout after
  merging the PvP privacy implementation. The website workfile records local
  verification and explicitly says it has not been deployed.

The shared contract was checked against DurisWeb's actual
`backend/src/services/pvpService.ts`, its SQL/API tests, backend/frontend types,
`frontend/src/views/BattleDetailView.vue`, and cache handling. The corresponding
documentation is `docs/api/README_api.md`, under “PvP participant snapshots”, and
`docs/ongoing-projects/2026-10-18-durisweb-pvp-privacy-workfile.md` in that repository.
The latter records the owner's accepted handoff. This plan adopts that implemented
contract; it does not leave schema naming or historical visibility open for a
different MUD implementation. No running binary or live deployment is verified here.

## Outcome and boundaries

For each participant, capture an authoritative publication decision on the game
thread and carry it with owned snapshots through the combat transaction. A
private participant contributes battle metadata and normal gameplay outcomes,
but no exportable equipment or log. Private conversation bodies must never enter
any participant's exportable POV, including an opted-in opponent's. An opt-in
must not publish text received during an earlier off interval.

Keep normal game output, personal recall, opponent visibility, reward accounting,
participant identity and team membership independent of publication consent.
Reuse `PlayerLog`, the player status save pipeline, the combat command codec and
transaction, and immutable migrations. No new export service, Redis ingestion,
toggle-history database, generic privacy framework, or durable command queue is
needed for these findings. Website query/UI repairs remain DurisWeb work.

Implementation is on `fix/pvp-publication-privacy`. The checkout is
production-labelled; all database and gameplay fixtures must be isolated, with
no live migration, restart or historical data edit. Production release remains a
separate authorized operation. The alignment checks below predate implementation.

### Implementation results

- Corrected whisper/ask body classification for sender and ordinary/telepathic
  recipients. Personal recall, actual delivery, language transformation, literal
  dollar handling, echo options and content-free observer notices are preserved.
- `PlayerLog` now tracks a bounded count of eligible trailing public messages.
  Accepted webinfo transitions start an empty export window; off-period writes
  cannot become eligible later. This reuses the existing buffer, with no copied
  history, new service or toggle-history store.
- Webinfo requests use the real status-save pipeline. Admission failure restores
  the flag and export window; admitted changes affect capture immediately and
  explicitly report pending persistence. Older failed writes do not undo newer
  live choices. Terminal failure/reconnect loads the last committed state.
- Capture freezes each participant's live permission once. Private capture skips
  equipment/log reads but retains battle/reward metadata. v4 carries explicit
  255/0/1 wire bytes; SQL receives NULL/0/1 in the existing transaction. v1/v2
  decode unknown with empty strings; v3 retains its original strings as unknown.
- Added immutable `0045_pkill_webinfo_at_capture`, bootstrap/manifests/boot contract,
  help, ADR clarification, runtime/migration documentation and the lifecycle
  inventory's publication purpose. Historical rows and prior migrations are intact.
- Both supported native engines passed fresh bootstrap/adoption, upgrade/replay,
  real repository rollback/retry/deduplication and runtime schema verification.
  Measured metadata fingerprints:
  - MySQL 8.0.46: `584eee807102151cffe0bd503d4bbc7599d51011b9a4bf06713b04e6b88671ea`.
  - MariaDB 10.11.11: `6a9c6e546ee14dc919584a64d77ae9a3f17b4498b0cf589a37680c1de98aeabb`.
- The shared journey passed using five actual MUD-generated capture commands,
  the real SQL repository and DurisWeb's anonymous routes/rendered UI. It covers
  mixed, both-on, both-off, public-empty and v3-unknown events, both kill directions,
  all current-state gates, quote/reply rules, release delay, invalid/absent consent,
  mobile/desktop views and service-worker cache retirement. Details follow below.
- The adjacent website's unrelated public-statistics work was preserved. Its
  owner committed it during this work; the final paired checkout is
  `e003097a1309f2e25d8e33364c9dc26f6559e3e4`, with the same merged PvP reader.
- No production migration, player-data edit, service restart, announcement or
  deployment was performed. Live operational acceptance remains the rollout below.

### Lifecycle review

`write_to_pc_log()` uses the resolved player (`GET_PLYR`), including switched
bodies; the executable fixture verifies that owner's flag. New logs initialize
with no eligible entries; `clear()` resets eligibility. Login's
`src/account/nanny.c` initialization calls `initialize_logs(ch, true)`, so reload
and copyover cannot infer eligibility from an old buffer. Ordinary reconnects
that retain the character retain its correctly classified live log. New-character
creation in `wiz_newchar.c` sets the unchanged default-on flag before any log
history exists. The existing default reset in `do_start_impl()` explicitly
resets an existing export window. No other production path changes this flag.

### Verification evidence

All fixtures used invented participants/text on loopback-only disposable databases.
Docker was unavailable to this shell; native MySQL 8.0.46 and MariaDB 10.11.11
provided the two real engine checks instead. Test binaries, logs, command files
and screenshots live only under ignored `bin/tests/`. Both disposable database
processes were stopped after verification.

| Check | Result and evidence |
| --- | --- |
| `python3 tests/async/test_combat_outcome_transactional_cutover.py` | 5 passed: real capture, duplicate discovery/owned snapshots, private equipment-read exclusion, export suffix bounds/eviction/reset, invalid-index fail-fast checks, v1–v4, malformed/private v4, sizes and key/revision validation. |
| `python3 tests/async/test_word_output_integration.py` | Passed real send/act/PlayerLog/capture with mortal participants and a positive public-output control; both sender settings, private channels, ordinary/telepathic delivery, echo, language, switched owner and toggle windows. |
| `python3 tests/async/test_player_save_pipeline.py` | Passed real dispatcher/status capture/codec/worker: admission rejection, capture failure, held writes, coalescing, captures before SQL completion, older-write failure, dirty retry, acknowledgement and successful/failed terminal-session recovery. Only the database boundary injects delays/failures. |
| `python3 tests/async/test_output_preferences.py`, `python3 tests/async/test_chat_log_privacy.py`, `python3 tests/async/test_toggle_dispatch_contract.py` | Passed reused preference/dispatch behavior and the separate server-log boundary. |
| `output_preferences_mysql_harness` on disposable MariaDB | Real status repository/load persisted act2 ON/OFF across reconnect; rollback retained the previous setting. |
| `bash tests/async/run_combat_outcome_schema_mysql.sh` on both engines | Passed exact stored 1/0/NULL, legacy text, old-writer NULL, malformed schema refusal, partial-insert rollback, retry, replay, rewards, full escaped/UTF-8 snapshots and legacy TEXT capacity upgrade. Expected negative verifier failures are part of the passing wrapper. |
| Fresh bootstrap/adopt/run and upgrade/adopt/run/replay on both engines | Passed actual `verify_runtime_compatibility.sh`; missing/renamed consent and SMALLINT consent refused before runtime admission, then canonical restoration passed. |
| Migration/runtime/lifecycle checks | 19 migration-runner tests, 7 boot tests and 12 lifecycle tests passed; both manifest validators passed. |
| Existing paired website regressions | 99 backend tests passed with none skipped; 14 mounted battle-view tests passed. |
| `python3 tests/async/run_pvp_web_handoff.py` | Shared anonymous API and real Chromium journey passed at 1440×1000 and 390×844. Synthetic JSON summaries and 12 screenshots are in `bin/tests/pvp-handoff/`; public/private screenshots were visually inspected. |
| `make -C src -j2`, `./scripts/format.sh --check`, `git diff --check` | Full native build and final incremental build passed; changed-line formatting and diff whitespace checks passed. |

Clang-tidy 21.1.8 and `clang-tidy-diff` were installed persistently in the staging
account's `~/.local/bin` using Ubuntu packages (this account cannot use sudo).
`./scripts/tidy.sh --rev origin/master` passed across all changed C/C++ lines.
Its exception-escape finding led to replacing the pre-existing invalid-log-index
throw with immediate termination on the same programming-error condition; valid
logging behavior is unchanged and both invalid bounds have executable checks.
Staged-line formatting also passed; no hook was bypassed.
The branch was rebased onto `89253179a` (current master); the upstream staff-purge
regression passed in both MySQL and flat-file harness modes.

The browser verified direct `pov` links, public equipment/logs, private/unavailable
messages, empty public logs, equipment and maximized views, and absence of private
or off-period markers. It activated the actual built worker over a seeded old
`api-cache`: PvP entries were removed, unrelated news remained, and refresh under
the controlling worker withdrew/restored a captured-public POV after saved OFF/ON.
No browser console or page errors occurred. This proves the paired local contract;
it does not certify the currently deployed website or a player's existing open tab.

The shared runner uses the existing native harnesses rather than a model of MUD
capture. To reproduce, provision an empty disposable `duris_test` schema using
`tests/async/disposable_schema.sh` (explicit `TEST_DB_*` settings), compile the
repository harness using `run_combat_outcome_schema_mysql.sh` on a separate
fixture, then run:

```bash
export PVP_CAPTURE_COMMAND_DIR="$PWD/bin/tests/pvp-handoff"
python3 tests/async/test_word_output_integration.py
# DB_* must name the disposable duris_test; ENVIRONMENT=test. This writes only
# the five synthetic handoff events and verifies their idempotent replay.
bin/tests/combat_outcome_mysql_harness
VITE_API_URL=http://127.0.0.1:48888 VITE_STATIC_URL=http://127.0.0.1:48888 \
VITE_WS_URL=ws://127.0.0.1:48888/ws pnpm --dir "$DURISWEB_ROOT/frontend" exec vite build \
  --outDir "$PWD/bin/tests/pvp-web-dist" --emptyOutDir
# Set DURISWEB_ROOT, TEST_PVP_DB_PORT, PVP_CHROMIUM and any local Chromium
# library path explicitly. The runner never loads either checkout's .env.
PVP_WEB_PORT=48888 PVP_WEB_DIST="$PWD/bin/tests/pvp-web-dist" \
  python3 tests/async/run_pvp_web_handoff.py
```

The frontend build uses Vite's existing configuration and explicit loopback API,
static and WebSocket overrides. The browser blocks other origins. The runner
creates its website test file exclusively, removes it in `finally`, and leaves
existing website files untouched. Native command/repository fixtures and the
website assertions use synthetic event IDs from `events.json`; no live IDs or
private text are copied into the shared fixture.

## Contract to implement

### Confirmed requirements

- `webinfo off` withholds the participant's entire POV: both equipment and log,
  including equipment text embedded in that log. It does not erase the event or
  other participants, prevent the player from reading permitted opponent POVs,
  or alter what anyone receives in the game.
- Capture the live participant's decision, not the viewer's flag or a later
  `player_data.act2` value. A later opt-in cannot authorize an earlier private
  snapshot or an off-period log buffer.
- Private message bodies remain private regardless of either player's setting.
- Queue admission is pending persistence, not a database acknowledgement.
  Missing historical snapshots and unknown historical consent are distinct from
  an explicitly private POV.
- DurisWeb reads **`pkill_info.webinfo_at_capture TINYINT NULL DEFAULT NULL`**:
  `1` permits consideration for publication, `0` denies it, and `NULL` is unknown.
  The initial plan's separate visibility column and 0/1/2 SQL encoding are
  superseded. Writing `2` as public would be incompatible: the reader withholds it.

### Implemented website policy to preserve

DurisWeb's `pvpPublicationSql()` applies the following rules to both log and
equipment before returning SQL rows. Its types expose the derived
`pov_status: 'public' | 'private' | 'unavailable'`; the MUD does not persist that
derived status or read the website admin setting during capture.

| Question | Required behavior |
| --- | --- |
| Later opt-out | With `respect_webinfo_toggle=true`, a captured-public POV also requires the current saved webinfo bit. A saved opt-out hides previously permitted POVs; later saved opt-in restores those POVs only. Captured-off/unknown rows never become public through a toggle. |
| Existing rows without captured consent | Mark `unknown` and withhold both fields by default, even if raw strings exist or today's flag is on. Do not backfill consent from current player rows. |
| `respect_webinfo_toggle=false` | Skip only the current saved-flag gate. A capture of `1` may be public; `0`, `NULL`, invalid values and absent schema remain withheld. This is not an owner/admin bypass of capture permission. |
| Missing/deleted current player row | A capture of `1` is unavailable with the current-state gate enabled and public with it disabled. A capture of `0` stays private; unknown/invalid stays unavailable. Retain the participant and permitted opponents. |
| Stored comment quotes | Text, line number and participant pointer follow the same gate, including replies; deleted comments and missing quote origins hide them. New quotes require a permitted log and valid line, and the server derives the text. Ordinary user-written comment bodies are not automatically rewritten. |
| Caches and open pages | PvP HTTP responses are `no-store`; the service worker uses network-only PvP reads and removes old PvP entries from `api-cache` on activation. Battle details have zero stale/unused-cache time. A refetch removes newly withheld payloads; open pages still require refresh and the updated worker. |

The following MUD implementation choices remain necessary to make a stored `1`
mean the payload is safe for that reader:

| Question | Planned MUD behavior |
| --- | --- |
| Buffer across toggles | Export only the bounded public-log suffix collected during the current uninterrupted on interval. Starting a new on interval starts a new export window; personal logs remain intact. |
| Directed `ask` bodies | Classify sender and recipient bodies as private, like whispers; keep content-free room notices public and NPC quest handling unchanged. No historical ask incident is claimed. |

New-character defaults are unchanged. The existing default-on setting is not
evidence of consent for old rows. Help must explain current-state withdrawal
when the website setting is enabled, its save latency, and restoration after
saved opt-in. Do not promise retraction of already downloaded content.

## Initial source and implementation targets (completed)

| Boundary | Current behavior and implementation target |
| --- | --- |
| [Combat capture](../../src/combat/fight.c) | `combat_outcome_add_participant()` always captures equipment and `read(LOG_PUBLIC, MAX_LOG_LEN)`. Gate both snapshots on live consent and read only the eligible export window. Preserve description/PID/role/level/in-room/leader fields. |
| [Player log](../../src/player/player_log.h), [delivery](../../src/net/comm.c) | Two bounded logs; `write_to_pc_log()` resolves `GET_PLYR(ch)` and writes messages. Add export eligibility at this boundary without changing ordinary reads or private recall. Styled output and `OutputChannel` do not determine confidentiality. |
| [Private channels](../../src/cmd/actcomm.c) | Whisper sender echo and both ordinary/telepathic recipient branches default to public. Supply `LOG_PRIVATE` or `ACT_PRIVATE` while preserving output contexts. Review `do_ask()` similarly; retain existing tell/reply, group, guild and alliance protections. |
| [Toggle](../../src/cmd/actoth.c), [save example](../../src/player/output_preferences.c) | `do_toggle()` flips `PLR2_WEBINFO` and calls a no-op. Use the existing status-save admission/rollback pattern and explicit pending/failure messages. |
| [Codec](../../src/combat/combat_outcome_command.h), [implementation](../../src/combat/combat_outcome_command.c) | Payload v3 owns snapshots but has no consent. Add participant `webinfo_at_capture` and v4 encoding, preserving v1–v3 decoding. Do not overload participation flags. |
| [Repository](../../src/combat/combat_outcome_repository.c) | Inserts snapshots inside the existing critical transaction. Persist nullable capture permission in the same participant insert; never fetch current flags on the worker. |
| [Runtime schema contract](../../src/core/runtime_compatibility_contract.h) | Current head is `0044_artifact_canonical_identity`; runtime requires exact metadata. Add the next available immutable migration and update bootstrap, manifests, measured fingerprints and boot checks together. |

## Implementation sequence

### 1. Correct message classification and export-window handling

Files: `src/cmd/actcomm.c`, `src/net/comm.c`, `src/player/player_log.h`; inspect
`src/cmd/actnew.c::do_gsay()` and `src/guild/alliances.c::do_acc()` as regressions.

- Change whisper body delivery for the sender and every recipient branch to
  private logging. Keep content-free bystander notices public. Apply the agreed
  directed-ask policy to all body-bearing branches. Preserve language handling,
  dollar escaping, echo settings, styling, and quest callbacks.
- Track the eligible suffix in the existing public log, for example with a
  bounded count of eligible trailing entries. At `write_to_pc_log()`, use the
  resolved player's live `PLR2_WEBINFO` state. Public writes while off reset the
  export window; public writes while on extend it within `PUBLIC_LOG_SIZE`.
  Private/`LOG_NONE` messages never become eligible.
- Add a bounded export read that respects that suffix and `MAX_LOG_LEN`. Keep
  ordinary `read()`/iteration behavior and `LOG_PRIVATE` recall unchanged. The
  current `clear()` clears both logs, so it is unsuitable for a toggle boundary.
  This needs neither a second copy of every message nor timestamped chat storage.
- Reset only export eligibility on an actual accepted toggle transition. Repeating
  `on` while already on must not discard the window. Initialize eligibility empty
  on log creation/reset; a missing log produces an empty snapshot. Check login,
  reconnect, copyover and character-reset/default paths so restored/unclassified
  text never becomes implicitly exportable. Inspect direct flag setters as well
  as `do_toggle()`; newly received off-period text must be excluded regardless
  of how the flag changed.
- Treat equipment output during an off interval like any other ineligible text.
  No regex-based equipment or conversation scrubber is needed: capture withholds
  the complete private POV and the export window excludes off-period content.

Proof: execute real delivery functions into a real `PlayerLog`, then capture a
POV. Test tell/reply/group/guild/alliance/whisper/ask sender and recipient bodies,
an opted-in recipient of an opted-out sender, normal and telepathic whispers,
bystander notices, echo off, language/escaping, and private recall. Seed unique
synthetic markers before/on/off/after toggles; assert excluded markers never
reach export while ordinary game delivery still works. Cover log eviction,
byte limits, repeated toggles, empty logs and lifecycle reset.

### 2. Persist `webinfo` through the supported status-save path

Files: `src/cmd/actoth.c`; remove the obsolete `sql_webinfo_toggle()` declaration
and MySQL/no-MySQL definitions from `src/sql/sql.h` and `src/sql/sql.c` once its
only caller is replaced. Reuse the pattern in `update_player_output_preferences()`
without expanding that unrelated API into a generic settings framework.

- Validate the existing on/off/toggle syntax before changing state. Preserve the
  pre-change flag, apply the requested state, and request
  `player_save_pipeline_request(ch, PLAYER_COMPONENT_STATUS, RENT_CRASH, room)`
  with the existing `NOWHERE`/room-vnum handling.
- On `queued`/`coalesced`, retain the new live flag and reset export eligibility
  for the transition. Report that the setting is active for new captures and the
  save is pending. Do not claim the website or database has acknowledged it.
  The website's historical-POV gate still uses the old saved flag until commit:
  an off transition immediately makes new captures private, but previously
  permitted captures may remain readable until the status write is acknowledged
  and the page is refreshed. With the admin gate disabled, that saved flag does
  not withdraw historical permitted captures at all.
- On admission/capture failure, restore the old flag, retain the old export
  window and report that the change did not take effect. An unsuccessful off
  request must never print the normal success confirmation. An unchanged request
  must not invent a committed acknowledgement for a previous pending request.
- Preserve the pipeline's existing later-failure behavior: a failed writer
  completion re-marks a live player's status for checkpoint retry and emits the
  persistence alert. Do not revert a newer setting when an older write fails.
  Keep queued versus written revision semantics explicit in messages/help;
  use the existing save acknowledgement path when durable confirmation is needed.
- Verify both normal disconnect/reconnect after commit and failed final saves.
  Current ended-session recovery can reload the last committed state after a
  failed write; do not promise survival of an uncommitted toggle across that
  boundary or a process crash. Document the actual loaded state and test it.

Proof: both directions, implicit toggle, invalid input, unchanged input,
queue rejection, capture failure, coalescing, older-write failure followed by a
newer toggle, retry, acknowledged save/reload, and failed terminal save/reload.
Capture immediately after an admitted toggle and before its SQL save completes:
the killer's and victim's POV decisions must follow their live flags even when
their separate status saves complete at different times.

After commit, verify the website's current-state gate follows `player_data.act2`
for historical captures of `1`; it never changes the stored capture field. Test
pending on while SQL is off, pending off while SQL is on, failure/retry and both
admin-setting values without claiming an immediate historical withdrawal.

### 3. Add the publication contract to schema, payload and capture

Required shared field: **`pkill_info.webinfo_at_capture TINYINT NULL DEFAULT NULL`**.
Use an explicit three-state `webinfo_at_capture` member in
`combat_outcome_participant`, initialized to unknown. An internal enum may use
unknown `-1`, off `0`, on `1`; serialize it explicitly and map unknown to SQL
`NULL`, never SQL `-1` or a string. Do not boolean-coerce unknown to on or default
legacy payloads to off through zero initialization.

| SQL value | Meaning | Anonymous API contract |
| --- | --- | --- |
| `NULL` | Unknown consent; pre-contract/legacy snapshot | `pov_status: unavailable`; both fields `null`, regardless of current flag or admin setting. |
| `0` | Private at capture | New MUD capture stores empty strings; `pov_status: private` and both API fields `null`, regardless of current flag or admin setting. |
| `1` | Safe, permitted capture | Public only after event release and any enabled current-state gate. A public POV returns stored fields; null/empty text means no snapshot was captured, not private. |

For a capture of `1`, the current-state truth table is:

| `respect_webinfo_toggle` | Current saved `act2 & 134217728` | `pov_status` | API `log` / `equip` |
| --- | --- | --- | --- |
| `true` | On | `public` | Stored values |
| `true` | Off | `private` | Both `null` |
| `true` | Missing player or null `act2` | `unavailable` | Both `null` |
| `false` | Any state, including missing player | `public` | Stored values |

Unknown is distinct from private and from missing content. API consumers must
fail closed for unrecognized states: SQL values other than `0`/`1` produce
`unavailable`. Missing schema also produces `unavailable`; an error reading
schema metadata fails the request closed. The field is per participant, not per
event, and only the website computes the effective status.

1. Add the next unused migration sequence (`0045_pkill_webinfo_at_capture` if
   still available) under `migrations/immutable/`, with guarded SQL and a verifier.
   Append the column so
   existing column positions, including migration 0041's log check, stay stable.
   Preserve old rows and text; old writers that omit the field get SQL `NULL`.
   Verify exact name, nullable `TINYINT`, and default `NULL`; DurisWeb's capability
   probe checks that exact column name on every relevant read. The website owns
   no migration or backfill for this column.
   Never edit an already recorded immutable migration or infer old consent.
2. Update `migrations/bootstrap_multithread_safe.sql`,
   `migrations/migration_manifest.json`,
   `migrations/runtime_compatibility_manifest.json` and
   `src/core/runtime_compatibility_contract.h`. Measure supported MySQL 8 and
   MariaDB 10.11 metadata fingerprints; do not guess them. Extend combat schema
   verification and fresh/upgrade/replay fixtures. Review the `pkill_info` entry
   in `migrations/data_lifecycle_manifest.json` for the documented publication
   contract without treating it as a decision on unrelated retention policy.
3. Bump `COMBAT_OUTCOME_PAYLOAD_VERSION` to 4 and encode capture permission explicitly.
   Decode v1/v2 with unknown consent and empty snapshots; decode v3 with unknown
   consent and its original strings. Preserve legacy key/revision validation,
   including the decoder's command rebuild. New live capture always supplies
   off/on; unknown remains available for legacy compatibility and persists as
   SQL `NULL`. Encoding the internal enum ordinal directly into SQL is forbidden.
4. Reject invalid enum values and v4 private entries carrying nonempty snapshots.
   Keep legacy unknown text decodable for replay, with its unknown state intact.
   Retain truncation/trailing-byte/NUL/size rejection and the existing
   15-participant, 65,535-equipment-byte and 99,999-log-byte limits.
5. At `combat_outcome_add_participant()`, freeze the live decision with the first
   snapshot. Private entries skip both `get_equipment_list()` and export-log
   reads. Public entries own bounded equipment and eligible log strings. Repeated
   participant discovery may merge roles/flags but must not recapture consent or
   strings. Set on/SQL `1` only with the corrected private-message classification
   and export-window handling in place; it is a publication guarantee, not just
   a copied flag. Character mutation/freeing after submission cannot alter the
   payload.
6. Write the decision with the snapshot in the existing repository insert and
   critical-command transaction. Preserve outcome/participant/ledger atomicity,
   operation identity, rollback/retry and replay deduplication. Do not add a
   second post-commit update or weaken gameplay accounting for private POVs.

Proof: mixed public/private/unknown fixtures, v1–v4 compatibility, malformed v4,
maximum sizes with escaped/UTF-8 text, character mutation after capture, and
duplicate participant handling. In isolated SQL, verify exact persisted values,
failure after partial insertion rolling back the entire operation, retry and
replay producing one event, and later current-flag changes leaving saved consent
unchanged. Preserve existing reward and legacy TEXT-to-MEDIUMTEXT tests.

### 4. Update player documentation and complete the DurisWeb handoff

Update `TOGGLE_WEBINFO` and relevant channel help in
`lib/information/help_index`: whole-POV scope, canonical `toggle webinfo on/off`,
pending versus durable saves, selected historical policy, and private message
classification. Explain that saved opt-out hides formerly permitted POVs when
the current-state gate is enabled, and saved opt-in restores only those permitted
captures. Replace the hard-coded 30-minute statement with wording referring to
the configured website release delay. Keep the documented default-on behavior
accurate.
Clarify the separate `PlayerLog` publication boundary in
[ADR 0003](../adr/0003-player-privacy-chat-snoop-addresses.md); its server-log and
command-debug checks alone do not prove PvP privacy.

DurisWeb already implements the field/value contract, derived API statuses,
desktop/mobile selectors, direct `pov` links, equipment/maximized views, quote
gating and cache behavior described above. Supply the completed MUD revision,
migration identity and synthetic capture/SQL evidence for unknown, off,
on-empty and on-populated POVs. Preserve event/PID identity and `inroom`: quote
origins join `event_id` plus participant PID, not `pkill_info.id`, and require
`inroom=1`. Stored quote text and line positions refer to immutable captured logs.

Include stored quote/reply reads, rejected private/unknown/invalid-line quote
creation, canonical permitted quote creation and later saved-flag changes in
the paired acceptance journey. Preserve freeform comment bodies. A missing
current player row, current flag or admin setting cannot supply capture consent.
No MUD implementation is an end-to-end privacy pass until the actual writer's
snapshots have passed through the anonymous API and rendered views together.

## Coverage of the October 16 audit

Current DurisWeb source and its API documentation already address these audit
findings. Preserve the resulting behavior as integration requirements rather
than scheduling duplicate repairs in the MUD. The table records source behavior
and the paired regression checks; it is not a production acceptance claim.

| Finding | Current DurisWeb behavior and MUD handoff |
| --- | --- |
| 1. Delayed secondary APIs | `pvpVisibility.ts` supplies the release cutoff and interaction-target check; service/profile queries use it. Fresh-event fixtures cover concealment then release. MUD preserves complete committed event/participant metadata, including private participants. |
| 2. Filters truncate teams/count mismatch | Separate matching-participant `EXISTS` and display aggregation retain complete teams. Only in-room participants match searches. Preserve PID, role and in-room fields. |
| 3. Description/prefix identity | Stable PID grouping, exact historical name resolution and deduplication before autocomplete pagination are implemented. Preserve PID and formatted historical descriptions. |
| 4–5. End-day and timestamp zones | Date-to uses an exclusive next-day bound; timestamps use database epochs serialized as ISO instants. Preserve the MUD UTC connection and event-stamp semantics. Retain calendar-boundary/non-UTC rendering checks. |
| 6–7. Notification route and polling | Links use `/pvp/:id`; `pvpPolling.ts` drains serial batches every 30 seconds with a timestamp/ID cursor. Restart starts at the latest visible event. Preserve event IDs/timestamps; no new MUD publisher is needed. Discord delivery has its own website queue and does not inherit the browser cursor. |
| 8. Search sort/pagination/validation | Routes now forward sort and normalize/validate pagination and advanced filters. Keep the route/SQL regressions; no producer contract change. |
| 9. Deleted-comment count | The API contract now explicitly counts retained thread slots, including deleted placeholders/replies. The SQL regression pins this choice; do not plan a decrement or a MUD counter change. |
| Additional limits | Matchup SQL no longer has the 1,000-row cap, and the fixture covers larger history. Battle dialogs use shared keyboard/focus/Escape primitives. Preserve the MUD's legacy `KILLER` mapping, which includes assists; do not reinterpret it as final blows. |
| Persistence limits | Preserve atomic commit and idempotent replay. The pre-commit queue remains in memory; this work does not establish crash durability. Battles lacking stored snapshots cannot be reconstructed by a reader upgrade. |

## Initial plan-alignment verification on 2026-10-18

The website predicate, schema probe, snapshot/quote queries, API types, UI state
selection and cache sources were inspected at the revision above. Existing
website tests were rerun from the DurisWeb root:

```bash
NODE_ENV=test TEST_PVP_DB_PORT=47483 pnpm --dir backend test --runInBand src/services/__tests__/pvpService.test.ts src/routes/__tests__/pvpIdValidation.test.ts src/services/__tests__/pvpPolling.test.ts
pnpm --dir frontend test:unit --run src/views/__tests__/BattleDetailView.spec.ts
```

Results: **99 backend tests passed, none skipped; 14 mounted UI tests passed**.
Port 47483 belonged to a newly initialized loopback-only disposable MariaDB
instance with synthetic records; it was shut down successfully after the tests.
These checks cover the implemented capture/current-state gates, anonymous API
payloads, stored/canonical quotes, absent-then-added schema, route/SQL correctness,
polling and mounted UI behavior. The decision tables above also follow the exact
branch order in `pvpPublicationSql()`.

The website worktree remained clean. No website build, format/lint/type check,
new browser/service-worker run, MUD build/gameplay test, migration on a game
database, historical-data edit or deployment was performed for this plan review.
Service-worker rollout remains a coordinated acceptance check; the workfile's
prior browser verification is not claimed as a new run. This establishes plan
alignment with the checked source, not completion of the pending MUD changes.

## MUD implementation verification worklist

Extend existing harnesses before adding new infrastructure. Use a focused native
privacy journey where no existing harness connects delivery, toggles and capture;
it must execute production paths rather than duplicate their decisions in a model.

| Check | Required additions and scope |
| --- | --- |
| `python3 tests/async/test_combat_outcome_transactional_cutover.py` | Real capture plus export-window and v4 codec cases. Replace the source assertion requiring unconditional `read(LOG_PUBLIC, ...)`; retain ownership, limits, transaction routing and legacy checks. |
| `python3 tests/async/test_word_output_integration.py` | Extend real send/act coverage to private body classification and actual `PlayerLog` writes; mocked delivery alone does not prove export privacy. |
| `python3 tests/async/test_chat_log_privacy.py` | Preserve server `LOG_CHAT` and debug-ring policy; this is a complementary check, not the new privacy journey. |
| `python3 tests/async/test_output_preferences.py` and `python3 tests/async/test_player_save_pipeline.py` | Preserve the reused save pattern; extend coverage through the real webinfo command for admission, coalescing, writer failure, retry and session recovery. Existing output-preference tests alone do not exercise webinfo. |
| `bash tests/async/run_combat_outcome_schema_mysql.sh` | Extend real repository/migration cases above. The current standalone wrapper provisions disposable MariaDB when `TEST_DB_HOST` is unset; never point it at a game database. |
| `python3 tests/async/test_immutable_migration_runner.py`, `python3 tests/async/test_runtime_boot_compatibility.py`, `python3 scripts/validate_runtime_compatibility.py` | Verify manifest/checksum/boot-contract changes, missing or malformed schema refusal, and separately measure both supported engines' fingerprints using disposable fixtures. |
| `./scripts/format.sh --check`, `make -C src`, `git diff --check` | Required after implementation. Keep compiled output under `bin/`. Report any unavailable engine or journey rather than claiming coverage from a static check. |

The final synthetic three-battle journey uses two invented participants A/B.
First verify the immutable stored capture decisions and their publication with
both saved current flags on, or with `respect_webinfo_toggle=false`:

| Capture | A capture flag | B capture flag | Expected published POVs after release |
| --- | --- | --- | --- |
| First | On | Off | A only |
| Second | On | On | A and B |
| Third | Off | Off | Neither; battle metadata remains |

Then change current saved state and test all three historical events again:

| Reader state | First battle | Second battle | Third battle |
| --- | --- | --- | --- |
| Current-state gate on, both saved off | Neither | Neither | Neither |
| Current-state gate on, both saved on again | A only | Both | Neither |
| Current-state gate on, A saved off, B saved on | Neither | B only | Neither |
| Current-state gate on, A missing, B saved on | A unavailable, B private | A unavailable, B public | Both private |
| Current-state gate off, any current flags/missing players | A only | Both | Neither |

Capture decisions never change; effective public visibility can. Inspect payload,
committed SQL, anonymous API fields, stored quote fields and desktop/mobile
controls. Add unknown/invalid/missing-schema fixtures, null current `act2`, public
empty logs, later opt-in and admin-setting changes. Cover direct links to hidden
POVs, private-message/off-period equipment markers, both kill directions and
delayed victim/survivor saves. Retain only sanitized evidence.

## Existing snapshots, rollout and rollback

1. **Containment first, in DurisWeb.** Deploy and verify the already merged
   reader before relying on the new producer. It withholds snapshots and stored
   quotes while `webinfo_at_capture` is absent or unknown, detects a later column
   addition without restart, and fails requests closed on metadata-query errors.
   Review the effect on historical viewing. Future MUD capture alone cannot
   contain already stored whispers or equipment embedded in old logs.
2. **Review historical content separately.** The investigation identifies six
   stored snapshots in battles 3–5 and confirmed whisper text in battle 3. Use
   owner-provided test history only for those specifically reviewed records.
   Even an otherwise permitted historical POV may contain misclassified chat;
   consent backfill alone is insufficient. Prepare a bounded, reviewable
   withdrawal/redaction proposal with affected IDs and sanitized counts, verify
   API/quote/cache/rendering removal, and obtain authorization before production
   data edits. Leave unrelated consent unknown and do not copy raw text into Git.
   Previously downloaded copies cannot be recalled by a server fix.
3. **Qualify locally/staging.** Complete code, migration, tests, help and shared
   contract before production approval. Confirm reader-first behavior, old-writer
   inserts defaulting to SQL `NULL`, and new-writer/new-reader behavior. Do not
   switch capture to v4 without the required schema and compatible reader.
4. **Coordinate the authorized release.** Prepare the build and supported-engine
   verification first. Plan quiesce/drain of in-memory combat and status writes,
   additive migration and runtime-contract update, and restart/copyover with the
   matching executable. Capture must not write `1` until the private-message and
   off-period-buffer fixes are part of that executable. Do not assume an old
   binary can restart against the new exact schema fingerprint or that queued
   v4 commands are readable by old code.
   Verify the actual running executable, migration head and empty initial export
   windows; checkout HEAD alone is insufficient.
5. **Verify the release.** With authorized synthetic gameplay, trace a newly
   committed battle through SQL, release delay, public/origin API and rendered
   POVs and quotes. Confirm persistence failure reporting and both capture/current
   visibility matrices. Activate the updated website service worker, verify old
   PvP cache entries are removed without removing unrelated cached news/forum
   content, and refresh open pages. Coordinate the website release's existing
   Website Changelog follow-up; this MUD plan revision publishes no announcement.
   External notifications and real player conversations are unnecessary fixtures.
6. **Rollback without reopening disclosure.** Keep website withholding in place.
   Stop/quiesce the new producer if needed and retain the additive schema and
   captured decisions and the mandatory capture gate. Use a build compatible
   with that schema; do not blindly restore the old fingerprint/binary or drop
   the column. Treat any rollback to
   an old capture path as unknown-consent output that the reader withholds.

### Bounded historical withdrawal/redaction proposal

The reviewed scope is **exactly six participant rows: both POVs in event IDs
3, 4 and 5**. The investigation records 9,575 equipment characters and 225,575
log characters across those rows, including seven outgoing whisper bodies in
event 3. These are prior sanitized counts, not a fresh production query.

Deploying the compatible reader and leaving their capture permission NULL
withdraws all six snapshots and their stored quote origins without editing the
text. Do not mark any of these rows public: owner-supplied toggle history alone
cannot establish that their old logs exclude private messages. This same unknown
gate safely covers unrelated legacy rows without inventing consent.

If permanent redaction is authorized separately, the proposed transaction is to
clear `equip` and `log` and set `webinfo_at_capture=0` on those six reviewed rows
only. Before executing, resolve and review their exact row/PID keys within event
IDs 3–5, require two expected participants per event and six affected rows total,
and abort on any mismatch. Keep event metadata, rewards and freeform comment
bodies intact. Verify anonymous detail/quote/reply responses and refreshed
desktop/mobile views with the updated service worker; do not preserve a raw text
copy in Git or claim recall of previously downloaded content. No historical-data
mutation is included in migration 0045 or performed by this PR.

The MUD implementation and paired local privacy journey satisfy the implementation
acceptance criteria above. Close the broader October 16 audit only after its
separate website findings and authorized deployed acceptance checks also pass.
This PR does not perform or certify the operational steps above.
