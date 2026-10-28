# Issue #417: full pwipe qualification and findings

Status: **completed local qualification after fixes**.
Four real full-world wipes were performed against the prepared local copy on
2026-10-28. The first exposed an unplayable recreated roster. Subsequent runs
qualified the repairs, actual authenticated world recovery, old-epoch rejection,
and both reward-preservation and reward-discard policies. The final source passed
wipe → staff login → fresh mortal/reward/combat/loot → save/reconnect → restart,
with exact saved scalar, item-identity and reward-link preservation.

## Result and scope

- Worktree: `/home/aiwithapex/projects/duris-issue417-pwipe`.
- Branch: `branch/issue-417-pwipe-qualification`.
- Final tested runtime source: `efcd7980ba5a0af5cf5bad7d9fa3bb2857a6d85d`.
- MariaDB development binary SHA-256:
  `ab40e7dcb6a83c31b2320236c8bd6ba844197654a0091fe6e8cbe55e006b3dc7`.
- Real target: `127.0.0.1:3306/duris_issue417`; initial populated dataset had
  281 base tables and approximately two million rows. The entire copied world,
  library and runtime were used, without `--minimal` for these real worktree runs.
- Final target state: **season 4 active**, local, healthy, ports **4000 / 4001 /
  4050** for telnet / TLS / WebSocket and health. The original Redis configuration
  is restored. `.env` remains `0600` and all credentials/runtime/recovery data
  remain uncommitted.
- The original reference was not repaired or reset by this task. Its invalid PID
  counter and five orphan account mappings remain reference-data findings.
  Its checkout and migration metadata changed independently while work continued.

This is qualification of the recorded branch and local configuration, **not a
100% reliability guarantee or production sign-off**. Newer master changes, the
primary allocator repair and an installed production/website cutover need their
own reviewed validation. No remaining reproduced wipe-blocking code failure was
observed in the final tested branch. The conditions and limitations below are part
of the result, not omitted failures.

## Actual full-world runs

1. **First run — 306.364 seconds** from final confirmed command through reset. SQL/filesystem completion succeeded, but recreated staff could not log in (F008). Evidence: `full-world/operator-state.json` and native launcher logs.
2. **Second run — 307.250 seconds** from final confirmed command through reset. Valid new PIDs and fresh gameplay worked; full-world spawn/prompt problems were recorded (F013/F016). Evidence: `full-world/replay-2/operator-state.json` and native launcher logs.
3. **Third run — 304.392 seconds** from final confirmed command through reset. Reset invariants, preserved rewards, post-wipe gameplay and world recovery passed with the staff/prompt fixes. Evidence: `full-world/replay-3/operator-state.json` and native launcher logs.
4. **Fourth run — 302.128 seconds** from final confirmed command through reset. Season 3 → 4 on the final allocator fixes, using the real discard-rewards policy. All reset invariants passed, all four old grants were deleted, and native gameplay created grant ID 5 and mortal PID 2,147,000,328. Evidence: `full-world/replay-4/`.

Each used the real `shutdown pwipe confirm yes` and an unaccelerated five-minute
countdown. Malformed commands were refused and an initial countdown cancelled
correctly. Independent SQL observation followed the active → resetting → SQL-ready
but fenced → active transition. Every completed launcher exited 55 and stopped for
an explicit new-season start.

For the original populated data, 59 of the 103 delete/reset tables contained
821,132 rows. All 103 were independently empty after reset. Account identity,
password, confirmation, blocking, flags and donation fingerprints were unchanged
for all 332 accounts. Four eligible Overlords were recreated on fresh valid PIDs;
old bodies and account mappings were retired. Outposts, nexus/timers, epic-zone
alignment and artifact state passed field-level reset checks. Filesystem inputs
were cleared/archived, original journal evidence retained, and old Redis epoch keys
removed. Protected baseline/history changes were limited to expected reset/boot
bookkeeping and appended fresh-staff baselines.

The third real run additionally included a linkdead mortal, four real account
reward grants, five old reward instances, and a real dropped shield in an
authenticated world image. Old instances/summon links were cleared; templates,
expiry and finite values were preserved under the recent-reset protection. Fresh
characters received distinct new UIDs with exact payloads. Duplicate summons were
refused; dismissal/cooldown survived reconnect and restart. After 5,810 seconds of
natural elapsed cooldown, login rematerialized the dismissed grant on a new UID,
and the explicit duplicate request was harmless. No clock was advanced for this
live cooldown test.

The fresh mortal moved through the authored world, killed an NPC, looted its actual
corpse, saved, camped out using the unchanged timer, reconnected and survived full
restarts with exact scalar state and semantic item graph. Staff now enter at their
hometowns with visible prompts. The old shield could not be found in the new season.
A further restart selected the current world generation while 57 authentic old-epoch
keys remained unchanged and unused; only those injected test keys were removed.

## Recovery proof

The first matched capture's SQL generation was unexpectedly rotated away (F009),
but an exact copy was recoverable from the separately hashed filesystem archive.
It was verified and frozen outside retention. The supported isolated importer then
exposed a source-owned view failure (F011) and five pre-existing orphan account
mappings (F012). After the scoped importer fix and an explicitly recorded five-row
correction in that candidate only, the full original world restored and its old
staff PID logged in/saved/logged out.

The richer season-2 capture subsequently restored **all 281 table checksums exactly
without any candidate data correction** in a separate socket-only MariaDB. Its
isolated Redis restored the exact authenticated generation 50; the real full world
booted, staff logged in, and the dropped shield returned with exact UID 163656577.
The primary reference was unchanged during this clean restore. All private candidate
daemons stopped afterward. Recovery used the reviewed one-hour world-image age
window, with original hashes/timestamps unchanged (F016).

## Findings and dispositions

### F001 — Populated-data cold boot exceeds short readiness probes

**Observed operational limit.** The original full dataset took about 241 seconds
to enter the game loop, chiefly while enumerating persisted item populations.
Initial 180-second probes expired while queries continued advancing. Later health
and login passed. Post-wipe full-world boot was much faster. No hang was inferred
from a probe timeout. Use an observed-process-aware boot window for this dataset.

### F002 — Mail recovery and telemetry disabled in the copied environment

**Expected configuration.** Native startup reported unavailable password-reset
mail because `MAIL_ENABLED` is false; telemetry is also disabled. They remained
unchanged in the final environment. Native mail isolation and loopback telemetry
season-transition tests passed separately; no live mail/telemetry deployment is
claimed. `error=0` telemetry status fields are not failures.

### F003 — Minimal fixtures alone could not establish full-world readiness

**Coverage gap closed for the main journey.** The initial supplemental synthetic
run was cancelled at the user's direction. Four real destructive full-world
worktree runs followed. Minimal fixtures remain supplementary fault/integration
coverage and are labelled as such.

### F004 — 81 deployment tables are outside the native lifecycle manifest

**Ownership classified.** All 200 declared native tables existed, but the full
copy contained 281 base tables. DurisWeb's source-owned baseline owns 71 extras.
The other ten are two Knex ledgers, two obsolete notification stores, three
`legacy_import_*` archives, and the retired `players_core`, misspelled
`prepstatment_duris_sql`, and `siege_objects` tables. The last three are empty.
Their checksums were preserved by the real wipes.

Current native source has no gameplay reader for those legacy stores. Its only
actual extra-table SQL reference is optional 30-day cleanup of website-owned
`account_login_history`. The correctly named prepared-statement store is empty.
These records are retained, not silently treated as native seasonal assets.
Evidence: `external-table-ownership.json`, `unlisted-native-references.txt`, and the
companion baseline at `759ce971e5d8f066f3156906b5101daaa8e8ab70`. Companion schema
adoption/retention remains its own deployment responsibility.

### F005 — Runbook referenced a removed mode and closed qualification issue

**Fixed.** `--redis --systemd` was documented despite the CLI no longer supporting
`--systemd`. Current qualification references still pointed to closed #264.
The runbook now describes the ordinary-user direct launcher and points current
qualification to #417 while retaining #264 as historical evidence.

### F006 — Some stores were empty in the initial full-data baseline

**Coverage expanded and scoped.** Initial data included 332 accounts, 881 account
links, 791 player rows, 50,388 player items, four pets, 121 banks, three guilds,
218 ships, 249 auctions and 553 shopkeepers. Rewards/summons, guildhalls, saved
floor items and corpses were empty, and world recovery was disabled.

The real worktree was subsequently populated through gameplay with rewards,
physical claims, a corpse/loot journey, a dropped floor item, authenticated world
images and a linkdead mortal. Native SQL/codec/launcher fixtures cover the remaining
populated optional stores, failures and replay paths. Empty-after-reset is never
used alone as proof for a populated-input case.

### F007 — Chaos starter benefits change fresh-season expectations

**Expected configuration.** The copied local configuration enables Chaos, all
creation races/classes, starter equipment/frigate/epic benefits and bank platinum.
Fresh mortals therefore received level 56, 20,000 epic points and a new million-
platinum bank balance. These were current-season grants, not restored old assets.
Normal-mode behavior was separately exercised by the supplementary runtime journeys.

### F008 — CRITICAL: wipe declared success with unplayable recreated PIDs

**Fixed and requalified.** The copied `player_data.AUTO_INCREMENT` was
4,294,000,104 although the largest stored player PID was 3,306. The reference has
the same oversized counter. The first wipe allocated IDs 4,294,000,104–107, but
native account/player APIs use positive signed integers. Staff appeared in account
menus, then received “Sorry, I couldn't load that character!” Health still said ready.

Pwipe now checks live capacity after writer quiescence and before the destructive
boundary, then rejects invalid active IDs/exhausted capacity at postflight. Native
cases cover signed-integer boundaries, the actual oversized counter and a late
allocator jump; incomplete work stays fenced. The real worktree was restored
**offline**, all 281 table checksums matched, and only its allocator was corrected.
An inventory of 86 explicit PID columns and 12 owner/actor/location columns found
maximum retained valid PID 2,147,000,304; fresh allocation starts at 2,147,000,305.
No retained valid identity was reused. The reference was not repaired.

Both SQL-engine matrices and the subsequent real staff/mortal journeys passed.
Do not blindly lower a live allocator to `MAX(player_data.pid)`; retained history
may contain higher identities. An already committed invalid roster requires a
verified matched restore rather than forcing activation or assuming resume repairs IDs.

### F009 — HIGH: ordinary backup rotation removed a matched recovery component

**Procedure fixed.** Preboot retention pruned the SQL generation referenced by the
first matched capture. The separately hashed filesystem archive fortunately
contained the exact generation; its recorded manifest hash and full verification
matched. Extracted custody modes were corrected to 0700/0600 after the verifier
properly rejected permissive extraction metadata.

Subsequent captures freeze the complete SQL generation outside managed retention.
The runbook now requires that frozen copy and its verified path/hash before pairing
filesystem/Redis supplements. Recovery cannot depend on an accidental backup-within-
backup. The original broken reference and successful recovery evidence remain private.

### F010 — MySQL cached allocator metadata bypassed the first repair

**Fixed and requalified.** The first MySQL 8 regression failed although MariaDB
passed: cached `information_schema.TABLES.AUTO_INCREMENT` hid an allocator change.
The owning MySQL session now sets `information_schema_stats_expiry=0` before the
safety read; MariaDB keeps its normal path. Both final matrices pass. See the
[official MySQL TABLES reference](https://dev.mysql.com/doc/mysql-infoschema-excerpt/8.0/en/information-schema-tables-table.html).

### F011 — HIGH: restricted full-schema restore rejected a source-owned view

**Fixed and requalified.** The actual dump's `players_view` DEFINER required
SUPER/SET USER when imported by the isolated schema owner. The restricted importer
correctly refused impersonation, but could not restore its normal captured schema.

The importer now rebinds only executable view-DEFINER dump metadata to CURRENT_USER,
preserving DEFINER/INVOKER mode and row bytes. The focused test covers both modes,
escaped identifiers and literal row text. The full captured-data isolated import,
reconciliation, authenticated world restore and login passed afterward.

### F012 — Five pre-existing orphan account mappings blocked reconciliation

**Data finding; reference unchanged.** Five non-deleted account links refer to
missing bodies (four PID-zero rows and PID 2740). No account was missing; there was
no account-owner mismatch, invalid artifact-mana row or erasure tombstone.
The first isolated candidate retained the exact five rows as evidence and marked
only those mappings deleted before qualification. Existing projection repair does
not retire missing-body links. No restore gate was weakened.

After real wipes retired old mappings, the richer season-2 capture restored and
qualified with **zero** candidate data corrections. Both outcomes are recorded;
the initial unmodified source was not falsely labelled clean.

### F013 — Recreated staff entered The Void with no exits

**Fixed and requalified.** Recreation preserved hometown but omitted `last_room`,
leaving SQL default zero, which is a real full-world room. It now initializes the
saved room from hometown and checks that invariant. Native cases and actual final
staff login verify the preserved home, rather than relying on a minimal-world room.

### F014 — Journey helpers assumed ordinary prompts and instant logout

**Corrected harness; no shortened live timers.** Chaos skips the Hardcore prompt
and ends with a Chaos equipment notice rather than the ordinary starter-kit notice.
The shared creation helper now accepts both actual flows. The first interrupted
attempt created no body; the next created the mortal successfully before the notice
expectation timed out. Subsequent creation/reconnect tests passed.

A normal mortal quit invokes the unchanged camp timer (about 140 seconds here),
not staff's immediate logout or a fixture's shortened timer. A combat script also
attempted camping before the paladin fight ended. A controlled reconnect/flee left
zero deaths, then actual save/camp/logout succeeded. `wear all` occupied both hands;
the cutlass wield refusal and initial punches were ordinary equipment behavior.
The real NPC kill, corpse coin loot and persistence were separately verified.

### F015 — Local clang-tidy/header selection blocked the commit hook

**Check environment corrected.** clang-tidy 18 selected GCC 16 standard headers,
while builds use GCC 13, producing parser errors and dependency SyntaxWarnings.
The hook passed with `--gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13` supplied
through the supported CLANG_TIDY override. No hook was bypassed and no product
NOLINT/suppression was added. Future local checks need a compatible toolchain.

### F016 — Blank fresh-staff prompt and recovery-window assumptions

**Prompt fixed; recovery variant explicit.** Fresh staff SQL rows also defaulted
`prompt` to zero. Recreation now supplies the standard visible prompt mask 14310;
actual final login shows it. Operator drivers use command-specific output rather
than assuming a character's personal prompt contains a literal `> `.

A five-second capture interval also reduced the derived default image age to 605
seconds. For the reviewed matched-recovery variant, the supported explicit age
window was 3600 seconds, as in the existing restore qualifier. Hashes/timestamps
were not changed. The shorter default was not claimed to accept an expired image.
Original Redis settings were restored at the end.

### F017 — The primary comparison checkout moved during qualification

**Scope constraint, not overwritten.** The primary checkout advanced independently
to `d84d48ec2` with unrelated dirty work. During the third run its migration-
history/state checksums changed; during the fourth, `divine_boon_state`,
`statistics` and `timers` also changed independently. It is a moving reference, not
an immutable control. The recorded schema comparison had the same 55-step prefix/hash.
This task issued only read-only queries to `duris_dev`. Frozen captures are the
comparison authority; this branch's qualification does not cover later master code.

### F018 — Shared allocator reads could reuse deleted identities on MySQL

A final audit found that player-name and account-reward indexes also use
`sql_next_auto_increment`, which still read cached metadata independently of the
pwipe-specific guard. An owned MySQL reproduction using the actual function
returned zero from cached metadata after deleting a seeded high ID 4096,
while the live allocator was 4097. The callers' fallback could therefore lose the
deleted-ID watermark. The player loader also narrowed the unsigned counter to an
`int`, allowing an oversized counter to wrap below existing IDs.

The fix shares the live-statistics read between normal allocation and pwipe,
refuses an unreadable allocator instead of silently falling back, saturates an
exhausted native PID range, and refuses new-character publication without a valid
PID. Existing characters remain usable when only the creation range is exhausted.
Fresh MySQL metadata can legitimately expose NULL for an untouched allocator;
COALESCE to 1 is now allowed only for a table with a declared AUTO_INCREMENT
column. Missing/non-auto tables, warnings and lost connections still refuse.

**Fixed and requalified.** Actual SQL regressions passed on MariaDB and MySQL,
including cached metadata, deleting IDs 1 and 4096, a fresh empty table and lost
connections. Sanitizer-backed player-index/admission checks passed. In the real
full world, setting the test allocator to 4,294,000,104 still allowed existing
staff login/save but refused new-character creation without a partial body or
account mapping; the saved valid counter was restored afterward. The fourth real
wipe then passed on the final source. With all old grants deleted, real native
staff creation allocated reward ID 5, and a fresh mortal received a new PID and
claimed that reward. The native handoff matrix and rebuilt flat-file refusal also
passed against the final source. Evidence: `allocator-live-refusal/` under
`full-world/`, `allocator-contract-final-*`, `source-contracts-final`, and
`full-world/replay-4/`.

## Operator incidents and expected diagnostics

- A raw candidate import incorrectly relied on the `mysql` database argument;
  the dump's CREATE DATABASE/USE statements selected the authorized **test worktree**
  instead. The empty candidate checksum gate caught it. The worktree game was
  stopped, the primary remained unchanged, and the target was restored consistently
  offline with all checksums verified before replay. Later candidates use the
  repository's separate socket-only MariaDB and restricted importer. The failed
  raw method is preserved read-only as `rehearse_restore.failed-attempt.txt`; its
  runnable script and the empty unused database/grant were removed.
- Read-only diagnostics hit an explicit UTF-8 collation mismatch, a nonexistent
  `loadroom` column (corrected to `last_room`), binary checksum UTF-8 decoding
  (corrected with explicit fields/HEX), and an overly exact reward marker predicate
  (markers also contain account/keywords). These changed no data.
- One restore retry referenced `dms_new` after launcher promotion; the verified
  runtime binary/stamp was selected instead. Two WSL login-shell calls exited before
  running commands; no-profile shell execution worked and was used afterward.
- The companion required a newer supported Node than the host's 24.14 and pnpm was
  absent. A private checksum-verified Node 24.15.0/pnpm 12.10.1 environment built an
  isolated checkout; the original website checkout/environment was not changed.
- Fourth-run read-only diagnostics initially queried `grant_id` instead of the
  grant table's `id`; the corrected query confirmed ID 5. A manual gameplay
  driver confused the displayed list ordinal with that stable grant ID, so
  `summon 5` was correctly refused; `summon 1` addresses the current list entry.
  The reward had already been granted automatically on fresh-character entry.
  The failed expectation and corrected journey are retained separately. A final
  diagnostic compared a tab inside a MySQL string with a raw field separator;
  selecting the two fields separately corrected that assertion without data changes.
- A during-countdown table capture was missed in the fourth run. Its independent
  baseline was reconstructed from the verified frozen **stopped pre-wipe** SQL
  in a disposable instance and is explicitly labelled as such. It is not presented
  as a concurrent capture. Continuous season observation and the full native
  launcher/operator transcripts remain available.
- Fourth-run discard eligibility used an explicit test-fixture timestamp 29 days
  before the run and `pwipe.preserve=false`; the original configuration and state
  were recorded. The ordinary five-minute countdown was unchanged. Original reward
  preservation configuration was restored before normal new-season gameplay.
- Chaos's level/death-risk, achievement and frigate notices are expected fresh grants.
  Disabled mail/telemetry notices remain intentional. A scheduler budget window
  reported 11 deferring pulses, 10,896 deferred callbacks, debt 2,521 and at most two
  late ticks; health stayed ready. About 42 GiB memory was available in the sampled
  host. These observations are not relabelled as wipe failures or full capacity proof.
- Expected injected SQL/Redis/filesystem errors remain in passing negative-test logs.
  Every unexpected failure and correction is retained in the private chronological
  `qualification-investigation-history.md` and per-case evidence.

## Build and execution context

The full-world build used development/MariaDB, g++ 13.3.0 and local MariaDB
10.11.14. Disposable SQL matrices used MariaDB 10.11.19 and MySQL 8.0.46.
The separate DurisWeb fixture used source `759ce971e5d8f066f3156906b5101daaa8e8ab70`,
Node 24.15.0 and pnpm 12.10.1. Mail/telemetry were disabled in the actual copied
world; their separately stated local fixtures are the relevant coverage.

From the named worktree, setup/build and operator entry points were:

```bash
make -j2 BUILD_PROFILE=development PERSISTENCE_BACKEND=mariadb
make world
./scripts/cycle_mud.sh --dev --check-config
./scripts/cycle_mud.sh --dev
# In-game, after account/staff authentication:
# shutdown pwipe confirm yes
# After the launcher exits 55 and completion checks pass:
./scripts/start_mud.sh --dev
./scripts/healthcheck.sh
```

Final incremental compilation used `make -C src -j2` with the same profile/backend.
The flat-file variant used that command with `PERSISTENCE_BACKEND=flatfile` and
`DMS_BINARY=/home/aiwithapex/projects/duris-issue417-pwipe/bin/server/dms_issue417_flatfile`.
Real-world evidence and recovery captures are under owner-controlled
`bin/analysis/issue417/full-world/`. They contain private player data and must not
be published. The final game runs through the transient user unit documented in
[the setup handoff](plan-issue-417.md).

## Final executable ledger

Each case passed (exit 0). In the recorded commands, `<worktree>` expands to
`/home/aiwithapex/projects/duris-issue417-pwipe`. SQL variants use the repository's
owned disposable database wrapper; MySQL cases select `TEST_DB_IMAGE=mysql:8.0`.
The website case prepends its private supported Node/pnpm runtime to PATH.
These overrides are scenario context, not credentials.

Each case passed (exit 0). `bin/analysis/issue417/<case>/result.json` holds its exact
command, revision, duration and output hash, alongside complete private output.
The four actual worktree runs and full-data restores have separate `full-world/`
records. Earlier successful cases ran before final commits but their applicable
code was unchanged; final matrices and runtime variants identify the committed
source explicitly. Failed predecessors remain evidence, not silently replaced passes.

- `lifecycle-manifest` — 1.337s. Command: `python3 tests/async/test_data_lifecycle_manifest.py`.
- `season-fence` — 0.027s. Command: `python3 tests/async/test_season_reset_fence.py`.
- `sql-completion` — 0.220s. Command: `python3 tests/async/test_sql_pwipe_completion.py`.
- `shutdown-command` — 1.957s. Command: `python3 tests/async/test_shutdown_broadcast.py`.
- `filesystem-cleanup` — 6.736s. Command: `python3 tests/async/test_cycle_pwipe_status.py`.
- `writer-quiescence` — 1.962s. Command: `python3 tests/async/test_pwipe_quiescence.py`.
- `mail-isolation` — 3.094s. Command: `python3 tests/async/test_pwipe_mail.py`.
- `redis-invalidation` — 0.171s. Command: `python3 tests/async/test_redis_pwipe_invalidation.py`.
- `restore-generation-contract` — 0.023s. Command: `python3 tests/async/test_pwipe_restore_generation.py`.
- `native-handoff-final-mariadb` — 68.301s. Command: `python3 tests/async/run_pwipe_handoff_mysql.py --server <worktree>/bin/server/dms`.
- `native-handoff-final-mysql` — 291.883s. Command: `python3 tests/async/run_pwipe_handoff_mysql.py --server <worktree>/bin/server/dms`.
- `writer-real-mariadb` — 86.557s. Command: `python3 tests/async/run_pwipe_writer_mysql.py`.
- `writer-real-mysql` — 111.070s. Command: `python3 tests/async/run_pwipe_writer_mysql.py`.
- `native-copyover-isolation` — 12.885s. Command: `python3 tests/async/test_copyover_evidence.py`.
- `maintenance-checkpoint-isolation` — 5.608s. Command: `python3 tests/async/test_maintenance_scheduler.py`.
- `locker-receipt-identity` — 3.965s. Command: `python3 tests/async/test_locker_receipt_recovery.py`.
- `flatfile-real-refusal` — 43.187s. Command: `python3 tests/async/run_pwipe_runtime_journey.py --flatfile-rejection <worktree>/bin/server/dms_issue417_flatfile`.
- `website-cutover` — 565.406s. Command: `python3 tests/async/run_pwipe_runtime_journey.py --redis --website <worktree>/bin/analysis/issue417/website <worktree>/bin/server/dms`.
- `redis-disabled-reenabled` — 517.643s. Command: `python3 tests/async/run_pwipe_runtime_journey.py --redis --redis-reenable <worktree>/bin/server/dms`.
- `discard-rewards` — 480.258s. Command: `python3 tests/async/run_pwipe_runtime_journey.py --discard-rewards <worktree>/bin/server/dms`.
- `telemetry-season-cutover` — 59.076s. Command: `python3 tests/async/test_telemetry_runtime_integration.py --posthog`.
- `backup-view-definer` — 4.533s. Command: `python3 tests/async/test_persistence_backup.py`.
- `discard-fresh-identities-mysql` — 491.754s. Command: `python3 tests/async/run_pwipe_runtime_journey.py --discard-rewards <worktree>/bin/server/dms`.
- `allocator-contract-final-mariadb` — 7.087s. Command: `python3 tests/async/run_sql_auto_increment_mysql.py`.
- `allocator-contract-final-mysql` — 11.839s. Command: `python3 tests/async/run_sql_auto_increment_mysql.py`.
- `native-handoff-allocator-final-mariadb` — 71.290s. Command: `python3 tests/async/run_pwipe_handoff_mysql.py --server <worktree>/bin/server/dms`.
- `flatfile-final-refusal` — 42.614s. Command: `python3 tests/async/run_pwipe_runtime_journey.py --flatfile-rejection <worktree>/bin/server/dms_issue417_flatfile`.
- `source-contracts-final` — 4.269s (reward contracts, player index/admission,
  SQL completion, writer quiescence, season fence and formatting).

The allocator contract cases and MySQL discard case ran with the pending allocator
changes before commit `efcd7980b`; their case metadata therefore names parent HEAD
`ffdf9a38b`. The final live world, native matrix, flat-file build/refusal and source
contracts ran after that commit. This distinction avoids treating a HEAD label as
proof that a test tree was clean.

The cancelled initial synthetic baseline exited 130 at the user's direction. The
first MySQL PID guard failed and was corrected. The actual first wipe's login
failure is F008. None is counted as a final pass.

The native matrices cover preflight/schema/dependency refusal, writer drain and
resume, commit uncertainty, mid-reset/launcher interruption, inherited locks,
wrong epochs, partial cleanup, same-epoch recovery, duplicate completion, fresh-file
preservation, rewards, ownership, collectors, boons, ships, mail and native inputs.
The website fixture additionally covers HTTP/session/presence/cache permissions,
WebSocket drain/reconnect and signed donation delivery/duplicate-credit refusal.
Telemetry uses local HTTPS receivers only. Flat-file coverage is safe refusal.

## Remaining rollout conditions and final handoff

- The tested local branch passes the requested real destructive journey after fixes.
  It is not a blanket 100% guarantee, a production-profile benchmark, installed
  website acceptance or certification of newer master changes.
- The reference's allocator/orphan mapping findings need separate review before
  operating that database. No primary repair or production operation was performed.
- Freeze matched recovery generations outside retention, use the isolated importer,
  reconcile source data explicitly, and choose a reviewed image-age window.
- The game remains local at season 4 with original Redis settings, `.env` 0600,
  verified TLS/WebSocket/health, and successful fresh-character persistence.
  Runtime/recovery files are uncommitted. Required recovery evidence is retained;
  unrelated primary work and the copied `lib/information/news` overlay are preserved.
- Source fixes are in commits `63ad7ac5f`, `07cfb7c4f`, `e8cb8c8e6`, `ffdf9a38b`, and `efcd7980b`.
  This report and the setup handoff provide the review trail for #417 and #97.
