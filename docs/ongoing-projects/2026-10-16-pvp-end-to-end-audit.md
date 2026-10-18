# PvP logs end-to-end audit — 2026-10-16

Tracking issue: [#31 — Fix remaining PvP log correctness gaps](https://github.com/LuminariMUD/DurisWeb/issues/31).
Notification delivery/polling work also overlaps [#30](https://github.com/LuminariMUD/DurisWeb/issues/30).

**2026-10-18 privacy correction:** the [three-battle webinfo investigation](2026-10-18-pvp-webinfo-privacy-investigation.md)
supersedes this report's broad privacy assurance. The checks below verified
current-flag filtering of the separate equipment field, not suppression of a
private player's whole POV. The follow-up confirms unconditional combat-log
publication, whisper text in a public snapshot, equipment disclosure inside a
log, and missing battle-time privacy state. The older observations remain a
record of what was tested, not proof of the owner's intended privacy contract.

## Verdict

**New combat logs are reaching the live website correctly, but the feature does
not pass a complete correctness review.** Capture, persistence, public log
delivery, equipment privacy, and desktop/mobile viewing work for the recent
battles inspected. Confirmed defects remain in delayed-event visibility,
filtering, statistics, dates, notifications, and comment counts.

This is an investigation and findings deliverable. No application repair,
production migration, configuration change, restart, deployment, backfill, or
live gameplay was performed by this audit. Tests that write data used a separate
disposable MariaDB instance. Browser notification fixtures were injected only
into the test browser; no message was sent to subscribers or Discord.

The [October 14 investigation](2026-10-14-pvp-missing-details-investigation.md)
described repaired source that was not yet deployed. That deployment status is
now historical: current production data, API behavior, and served frontend
assets demonstrate that the snapshot and historical-display repairs are active.
The old report's statement that no migration was needed is also historical;
current MUD source includes migration `0041_pkill_log_capacity`, and production
already has the required `MEDIUMTEXT` log column.

## Scope and evidence boundaries

Inspected the website source, compiled/served assets, public HTTPS and local
origin responses, live database in read-only transactions, paired MUD capture
and transaction code, executable codec/SQL tests, and real browser interactions.
The configured `MUD_DIR` identifies the separate game repository; this checkout
is the website. PvP ingestion uses MUD-owned SQL tables, not a missing Redis
subscription or a website import job.

Source revisions at inspection:

- Website: `98379c89e43e113284b796289e280b713ad2b0c1`.
- MUD: `b149b3ada6e8c9c1e041ad864772195173fef7c6`.

Both worktrees started clean. During this audit, independent edits appeared in
`backend/src/routes/pvp.ts`, its route tests, and `docs/api/README_api.md`.
Those pagination changes were preserved, inspected, and included in the final
focused test run. They were still absent from live API behavior on the final
probe. This report does not claim authorship or deployment of those edits.

Live executable identity and service state were inspected; checkout HEAD alone
is not proof of the exact running MUD revision. Runtime hashes, screenshots,
and temporary test tooling remain outside the checkout. No participant names,
account identifiers, raw combat logs, credentials, or player records are included
here. Observations were made on October 16, approximately 10:03–10:15 UTC.

## What works in production

The database contained five events and eleven participant rows, with no orphaned
participants or empty events. All five events link to `combat_outcome`. All
eleven participants are in-room records. The six participant rows belonging to
events 3–5 have formatted descriptions and nonempty log/equipment snapshots.

| Battle | Participants | Stored log lengths, characters | Stored equipment lengths, characters | Public equipment snapshots |
| --- | ---: | ---: | ---: | ---: |
| 1 | 3 | 0 | 0 | 0 |
| 2 | 2 | 0 | 0 | 0 |
| 3 | 2 | 37,028–46,321 | 1,739–1,923 | 1 |
| 4 | 2 | 35,068–46,020 | 1,413–1,716 | 1 |
| 5 | 2 | 27,475–33,663 | 1,285–1,499 | 1 |

- Every participant's live API `log` equals its stored SQL snapshot exactly.
  Every API `equip` equals the snapshot when the player's visibility bit is
  enabled and is `null` otherwise. `respect_webinfo_toggle=true`; only three
  participant rows currently permit equipment disclosure.
- `pvp_delay_minutes=15`. Main list/search/detail queries apply the delay.
  A fresh isolated event is absent from the list and its detail lookup returns
  `null`, while older events remain available. Current production events were
  already older than the delay, so this boundary was exercised with fixtures.
- All five live detail APIs return HTTP 200. List, search, leaderboard,
  autocomplete, analytics, comments, and interaction-stat responses checked
  through the public tunnel match the local origin. Both health endpoints return
  200; their changing health metadata is not asserted to be identical.
- Numeric level search finds historical name-only records. Player autocomplete
  returns six identities; the kills leaderboard returns five entries without
  blank names. Invalid detail ID `0` returns 400; a valid nonexistent ID returns
  404.
- Public HTML references the local served entry asset; the public battle-detail
  JavaScript chunk matches the corresponding served file byte for byte.
- Browser list → **View Details** → battle 5 → alternate POV works. The URL's
  `pov` parameter changes, logs render with colors, equipment and maximized-log
  dialogs open/close, and battle 1 explains missing logs and privacy-hidden
  equipment. Mobile equipment/comments/log tabs work at 390 × 844.

### Capture and persistence contract

In the MUD, `src/combat/fight.c:820` captures formatted identity, bounded
equipment, and `PlayerLog::read(LOG_PUBLIC, MAX_LOG_LEN)` on the game thread.
`combat_outcome_command.h` defines payload v3 with owned strings, up to fifteen
participants, 65,535 equipment bytes and 99,999 log bytes per participant.
Legacy v1/v2 payloads decode with empty snapshots. The repository writes event,
participant snapshots, outcome, and associated ledger changes within the
critical-command transaction; replay is idempotent.

Current production `pkill_info.log` is nullable `MEDIUMTEXT` and `equip` is
non-null `MEDIUMTEXT`, both `utf8mb4`. The MUD SQL harness passes maximum-size
and escaped-content storage, rollback/retry, replay, and legacy TEXT-capacity
upgrade checks. The codec suite passes all five tests.

The earlier persistence limit remains: successful commit is atomic, but the
pre-commit queue is in memory. This audit does not establish crash survival for
accepted commands that have not committed. It also does not establish recovery
of the missing snapshots in battles 1–2. Deploying a reader cannot recreate
historical text that was not stored.

## Findings requiring follow-up

### 1. High — delayed battle information is available through secondary APIs

The advertised setting says how long to wait before showing new battles.
Only `getPvPEvents` and `getPvPEventDetail` in
[pvpService.ts](../../backend/src/services/pvpService.ts) load/apply that delay.
Leaderboards, player statistics, autocomplete, analytics, favorites, comments,
and interaction counts do not consistently enforce it. The character-profile
history query in `forumService.ts:2638` also lacks the cutoff.

**Executed reproduction:** with a synthetic event stamped `NOW()` and a
15-minute delay, list/detail conceal it, but leaderboard and player statistics
identify its participants; player/location autocomplete and timeline include
it; favorites expose its event ID; comments and interaction stats are readable.
The fixture can also favorite/comment on it before release. Character-profile
history was source-reviewed, not separately fixture-executed.

This is early disclosure of battle metadata and interactions; it is **not**
evidence that the detail API exposes embargoed raw logs or private equipment.
Apply one visibility rule to every public battle-derived read and interaction
target. Add a fresh-event test across the complete public route set.

### 2. Medium — participant filters remove other participants from the result

`getPvPEvents` filters the same `p` rows used by `GROUP_CONCAT` to construct teams.
Filtering by player, class, race, level, or alignment therefore produces partial
battle cards instead of complete teams for matching battles. Count and data
queries also differ: the data join requires `inroom=1`, the count join does not.

**Live reproduction:** filtering for one historical killer returns a card with
one killer and zero victims, despite its detail having two killers and one
victim. **SQL reproduction:** filtering for an out-of-room participant reports
`total=1` with zero returned events.

Select matching event IDs using an `EXISTS` predicate or separate participant
alias, then aggregate all displayable participants. Align count/data eligibility
and explicitly decide whether out-of-room participants should match searches.
Cover all participant filter types and both team sizes in regression tests.

### 3. Medium — statistics use descriptions and prefix matching as identity

`getLeaderboard` groups by the entire `player_description`. A level, class,
guild, or formatting change can split one PID into multiple standings entries.
`getPlayerStats` uses `LIKE '%] NAME%'`, allowing a name to match a longer name.

**SQL reproduction:** the same PID captured as level 50 and level 51 becomes two
one-kill leaderboard entries. Querying synthetic `Alpha` also counts the death
of `Alphabeta`, yielding two kills/one death instead of two kills/zero deaths.
One live PID already has multiple descriptions, but the current live kills
leaderboard itself has five distinct names; duplicate live standings are not
claimed.

Aggregate by stable battle participant identity, choose presentation metadata
separately, and perform exact name resolution. Preserve historical records when
current character rows are absent. Autocomplete similarly deduplicates names
after SQL pagination, which can yield short/incomplete pages as history grows.

### 4. Medium — “Date To” excludes almost the entire selected day

The UI sends a date-only value. `getPvPEvents` compares it with `e.stamp <= ?`,
which treats that date as midnight at its start.

**Live reproduction:** `date_from=2026-10-16&date_to=2026-10-16` returns zero;
changing only `date_to` to `2026-10-17` returns the three October 16 battles.
A noon SQL fixture on a selected single-day range is also excluded.

Define the timezone of calendar filters and translate the end day into an
exclusive next-day bound. Test midnight, midday, and the following midnight.

### 5. Medium — timezone-naive API timestamps are parsed as browser-local time

Database `NOW()` and UTC agree on this host. The API returns strings such as
`2026-10-16 03:34:39`, without an offset. Both PvP views call
`format(new Date(dateString), ...)`.

**Browser reproduction:** in `America/New_York`, the battle time parses to
`2026-10-16T07:34:39.000Z`, four hours after the stored UTC instant. The display
continues to show the server wall-clock hour without explaining that convention.

Publish timestamps with an explicit timezone and choose either clearly labeled
server time or correctly converted local time. Test at least UTC and a non-UTC
browser, including date boundaries. Do not change historical values by treating
current character or browser settings as evidence of their original timezone.

### 6. Medium — in-app and browser notifications link to an unsupported route

[App.vue](../../frontend/src/App.vue) and
[useNotifications.ts](../../frontend/src/composables/useNotifications.ts) use
`/pvp/battle/:id`; the router defines `/pvp/:id`.

**Browser reproduction:** inject a synthetic `NEW_PVP_EVENT` into the browser's
intercepted socket, click **Click to view details**, and navigation reaches
`/pvp/battle/5` without rendering the battle. Directly opening that URL fails the
same check. The same injected event successfully invalidates/refetches the PvP
list, so the client refresh callback works.

Use the canonical battle route in both notification paths and add a click-through
test. `pushNotificationService.ts` already uses `/pvp/:id`; do not conflate that
separate push-delivery path with the two broken links.

### 7. Medium — notification polling couples release delay to polling frequency

In [index.ts](../../backend/src/index.ts), `checkForNewEvents` fetches only one
latest visible event. The timer interval is `pvpDelayMinutes * 60 * 1000`, fixed
at startup. This is source-confirmed behavior, not a measured live burst test.

- At the current 15-minute delay, an already-open page may wait roughly another
  polling interval after a battle becomes eligible. Multiple newly eligible
  events produce a notification only for the latest one.
- Changing the delay does not recreate the running interval. A zero-delay start
  supplies `setInterval(..., 0)`, resulting in a rapid timer rather than a sensible
  independent polling cadence. Async polls can overlap.

Use a positive independent interval, prevent overlap, and fetch every event
after the cursor in a deterministic order. Test zero delay, changed settings,
multiple events per poll, reconnect, and timestamp ties. No production setting
was changed to exercise the zero-delay case.

### 8. Medium — advanced search drops sort order; live pagination is inconsistent

The frontend sends `sort_by=likes` to `/search` when advanced filters are active,
but that route does not put `sort_by` into `SearchFilters`. An isolated route
probe confirms `/events` forwards `likes`, while `/search` forwards no sort.
Thus **Popular** silently becomes date order when an advanced filter is used.

Other live probes: `/api/pvp/players?limit=-1` returns 500, and
`/api/pvp/search?limit=1000` reports a limit of 1000 while the service caps its
query at 100. Nonnumeric level filters are silently ignored.

**Concurrent work:** the independent source changes now normalize pagination
across these routes; their added tests pass in the final run. Final live probes
still reproduce the 500 and inconsistent limit. Sorting and level/date filter
validation remain separate gaps. Validate filters centrally, forward sort order,
and verify normalized response metadata after any separately authorized release.

### 9. Low — deleting a comment does not update the stored comment count

`createBattleComment` increments `pkill_event.comment_count`;
`deleteBattleComment` only marks the comment deleted. No production trigger
maintains these counters.

**SQL reproduction:** create and delete one comment; stats still report one
comment while no nondeleted comment remains. The API returns a deleted
placeholder, so decide explicitly whether the badge counts visible contributions
or retained thread slots. If it is intended to count active comments, decrement
atomically and idempotently; account for replies and repeated deletion.

Current production has zero comments, likes, and favorites, with consistent
counters. This is a fixture-confirmed behavior, not an existing live-count
incident. Like/duplicate-like/unlike transactions passed the fixture lifecycle.

### Additional limits

- Class-matchup analytics reads at most 1,000 matchup rows without deterministic
  ordering. Its totals are not a complete-history guarantee at larger scale.
- Group-side `KILLER` semantics include assists; the MUD maps killer-group roles
  to that legacy string. Do not reinterpret these statistics as final blows
  without a deliberate contract change.
- The existing custom dialogs lack dialog semantics and Escape-key dismissal.
  Mouse close controls work. Keyboard/accessibility qualification remains open.

## Browser verification

Browser plugin not available. Used existing cached Playwright and Chromium
140.0.7339.186 with its existing local library directory; installed nothing.
Public HTTPS was used with real production APIs except the explicitly described
browser-only event and long-log fixtures.

| Check | Result |
| --- | --- |
| Route/title identity and meaningful content | Passed for `/pvp`, `/pvp/1`, `/pvp/5` |
| Framework overlay, page errors, console errors/warnings, failed HTTP responses | None observed in the final main flow |
| Desktop 1440 × 1000 | List, detail, POV switch, equipment, maximize, close passed |
| Mobile 390 × 844 | Detail, equipment/comments/log tabs passed; no page-width overflow |
| Historical empty state | Missing log and privacy explanation rendered correctly |
| Long-log fixture | 1,000-line preview expands to all 1,501 synthetic lines |
| Browser event fixture | List refetch passed; notification navigation failed as finding 6 |
| Non-UTC context | Reproduced finding 5 |
| Screenshots | Desktop/mobile and equipment/empty-state evidence inspected; retained privately outside Git |

Initial automation assumed anchor-based list navigation and standard dialog
roles/Escape handling. Those assumptions were corrected to the actual **View
Details** and **Close** controls before reporting the final results. The remaining
notification failure is an application defect, not a locator timeout.

## Commands, results, and limitations

Commands ran from the website root unless stated otherwise. `$PVP_AUDIT_DIR`
denotes the private temporary directory outside both checkouts. The disposable
SQL server used loopback port 34897 and fixture-only credentials; production
credentials were loaded only in memory for read-only inspection.

| Command / probe | Result |
| --- | --- |
| `TEST_PVP_DB_PORT=34897 pnpm --dir backend test --runInBand src/services/__tests__/pvpService.test.ts src/routes/__tests__/pvpIdValidation.test.ts` | Initial 16 passed; final 52 passed after concurrent pagination tests appeared; all three real SQL contract cases ran |
| `pnpm --dir frontend test:unit --run src/views/__tests__/BattleDetailView.spec.ts src/utils/__tests__/ansiParser.spec.ts` | 15 passed |
| `pnpm --dir backend format:check` | Passed, 281 files |
| `pnpm --dir backend lint` | Passed |
| `pnpm --dir backend type-check` | Passed |
| `pnpm --dir backend verify:mud-writes` | Passed, 53 classified writes |
| `pnpm --dir frontend format:check` | Passed, 642 files |
| `pnpm --dir frontend lint` | Passed |
| `pnpm --dir frontend type-check` | Passed |
| `./scripts/check-config-literals.sh` | Passed |
| MUD: `python3 tests/async/test_combat_outcome_transactional_cutover.py` | 5 passed |
| MUD: `TEST_DB_HOST=127.0.0.1 TEST_DB_PORT=34897 TEST_DB_USER=<fixture-user> TEST_DB_PASSWORD=<fixture-password> bash tests/async/run_combat_outcome_schema_mysql.sh` | Passed: snapshots, limits, rollback/retry, replay, ledgers, legacy capacity/preservation tests |
| `node "$PVP_AUDIT_DIR/live-audit.mjs"` and inline Node mysql2/HTTP probes | Live inventory, public/origin comparison, schema/settings, exact SQL/API content and privacy comparisons, date/validation reproductions |
| `node "$PVP_AUDIT_DIR/sql-audit.mjs"` | Current service source transpiled into a temporary module with an isolated SQL pool/settings adapter; reproduced findings 1–4 and 9 and verified privacy/like lifecycle |
| `node "$PVP_AUDIT_DIR/route-audit.mjs"` | Current Express router with a recording service adapter confirmed dropped search sorting |
| `LD_LIBRARY_PATH=<existing-browser-libraries> node "$PVP_AUDIT_DIR/browser-audit.mjs"` | Seven main checks passed; unsupported notification URL check failed |
| Same invocation for `browser-probe.mjs` and `browser-events.mjs` | Page diagnosis; client-only socket event, timezone and long-log checks |
| `git diff --check` and report-link checks | Passed on final documentation review |

Supporting commands: `pwd`, `rg --files`, `rg -n`, `cat`, `sed`, `head`, `tail`,
`ls`, `command -v`, `ps`, `git status --short`, `git diff`, `git diff --stat`,
`git rev-parse HEAD`, and corresponding read-only `git -C` calls in the MUD;
`systemctl [--user] show/list-units` inspected state. Python helpers inspected
`/proc` executable identity/hashes, checked the unused fixture port, and edited
temporary probe scripts. `mktemp -d`, `mariadb-install-db --no-defaults`, and
`mariadbd --no-defaults` created/ran the disposable instance. Fixture setup issued
CREATE/INSERT/UPDATE/DROP only there. `mariadb-admin --no-defaults
--socket=<temporary-socket> -uroot shutdown` stopped it, and the process handle
confirmed exit. `chmod 700` protects the temporary evidence directory.

Discovery/diagnostic failures: project-local `pnpm --dir frontend exec playwright
--version` was unavailable; cached tooling worked. Several guessed source paths
were absent. The first settings query used incorrect column names and was
corrected to `setting_key`/`setting_value` inside a read-only transaction. The
first MUD SQL invocation supplied a password to the disposable server's
passwordless root; it failed authentication before setup, then passed using a
dedicated fixture user. A temporary browser script had a syntax error before
launch; it passed after correction. Negative schema-verifier messages in the
MUD harness are expected refusal cases; the final command exited zero.

Not run: full package suites, new production builds, production preflights,
live authenticated likes/favorites/comment posting, real combat generation,
live delayed-release/burst timing, external notification delivery, crash/restart
recovery, or other browser engines. Existing unit route authentication is
mocked; isolated service mutation tests do not establish live account/session
authorization. Builds were unnecessary for this documentation-only audit and
would risk replacing served artifacts in this production checkout. Package
configuration and palette gates were not run because no configuration or UI
source was changed by this audit. No Website Changelog entry is needed for
this findings-only deliverable.

## Suggested repair order and acceptance

1. Close delayed-event disclosure across all public surfaces; use fixtures to
   prove both concealment before the cutoff and release afterward.
2. Correct event selection/team aggregation, stable player identity, inclusive
   calendar dates, explicit timestamp zones, and advanced-search sorting.
3. Fix notification routes and independent polling/cursor behavior; cover a burst
   of events and a real rendered click-through without sending external messages.
4. Finish/review the separate pagination repair and decide comment-count semantics.
5. After an authorized release, repeat the public/origin/browser checks and verify
   a newly committed battle from SQL through delayed public rendering. Preserve
   equipment privacy and document historical snapshots that remain unavailable.

Keep live gameplay, external notifications, and recovery exercises separate from
this read-only production investigation. These findings are not a claim that
every failure mode or authenticated interaction has been qualified.
