# Issue #264: qualify the full pwipe lifecycle

Status: implementation started 2026-10-24; full wipe readiness remains OPEN.
Prepared 2026-10-23 for [#264](https://github.com/LuminariMUD/Duris/issues/264),
the **Wipe system** readiness item in [#97](https://github.com/LuminariMUD/Duris/issues/97).
Implementation branch: `branch/issue-264-pwipe-qualification`.
Source baseline: [master `e2a2166f34fc`](https://github.com/LuminariMUD/Duris/commit/e2a2166f34fc56b814d553feed0a43d952b4a4d2).
Issue #264 had no comments when inspected. This plan covers its seven review areas,
four verification requirements, and four completion criteria. The latest master #245
plan is preserved in [plan-issue-245.md](plan-issue-245.md).

## Outcome, non-goals, files, and proof

**Outcome:** one supported, recoverable pwipe workflow that resets precisely the
agreed seasonal state, preserves approved carryovers, remains fenced after an
incomplete reset, and reaches a playable new season without old state returning.
Readiness requires command -> launcher -> filesystem -> startup -> fresh character
-> save/rent -> reconnect -> second reboot evidence, plus failure/retry evidence.
A SQL success message or passing source checks is insufficient.

**Non-goals:** production wipe/deployment, general persistence redesign, a new
wipe service/framework, privacy-retention policy changes, deleting audit history
merely because it is old, unrelated cleanup, and adding a new flat-file pwipe
feature. Existing flat-file builds reject this command; qualify that rejection
and document the support boundary. The issue requires supported modes and coverage
gaps to be recorded, not an invented promise of backend parity. A later request for
flat-file wipe support requires an explicit scope extension and revised estimate.

**Files:** start with `src/cmd/actwiz.c`, `src/sql/sql.c`, `src/net/comm.c`,
`scripts/cycle_mud.sh`, `Players/wipers/wipe_it_all`, and
`deploy/systemd/duris-mud-production.service.in`. Follow the writer/replay/retention
consumers below; change them only where a reproduced failure or reset requirement
needs it. Use existing lifecycle/migration manifests, additive migrations if needed,
`docs/operations/RUNBOOK.md`, `docs/operations/CONFIGURATION.md`,
`docs/testing/REGRESSIONS.md`, and focused `tests/async/` tests. Keep this plan current.

**Proof:** disposable MariaDB/Redis, private runtime directories, synthetic accounts;
real server/launcher execution; targeted writer/failure tests; SQL/filesystem/Redis
postconditions; new-season gameplay; required builds/formatting. No production
operation is authorized by this plan. No C/C++ build or destructive runtime test
was run during planning.

## Current continuation — matched pre-wipe restore

Branch `branch/issue-264-matched-restore`, based on PR #336 at `24d68b3d8`.
Outcome: rehearse a frozen pre-wipe SQL/journal generation paired with legacy
filesystem and real authenticated Redis world-recovery data; restore all three
into fresh owned candidates, prove original epoch/bodies/banks/rewards/files/world
and account access, and leave the wiped new-season source unchanged. Extend the
existing executable runtime journey with an optional restore stage and document
the manual cutover. Reuse backup capture/verifier, private DB import/reconciliation,
tombstone gate and native receipt verifier; do not add a backup coordinator or
production promotion feature. All writers are stopped across the frozen capture;
a verified SQL-only generation alone is not a matched wipe backup.
Files: existing runtime journey, runbook/regression notes and this plan. Proof:
actual command/reset/fresh gameplay, matched hashes/epoch, independent SQL import,
real Redis RDB restart/recovery, restored account login/save/reconnect, unchanged
source and retained generation. Production action and full readiness are excluded.
The first trial captured a verified SQL generation and real authenticated world RDB,
then passed command/reset/filesystem cleanup; fresh gameplay/recovery is running.
The fixture was tightened during review to give the restored Redis its own port
and retain the post-wipe source for comparison. Run that final fixture before
claiming the full matched restore. No C/C++ source changed; reuse #336 builds.

## Current continuation — same-epoch SQL resume

Branch `branch/issue-264-sql-resume`, based on PR #334 at `613d15aa5`.
Review-ready [PR #336](https://github.com/LuminariMUD/Duris/pull/336), implementation
`9720c98f9`; both-engine evidence committed at `b8479d01a`.
Outcome: a SQL-only native recovery command verifies the existing sealed schema and
runtime exclusion guard, resumes only the exact unfinished checkpoint-aware reset,
and returns SQL-ready without starting the world. Reuse the reset body, skip a
committed roster, retain the fixed epoch/reward boundary, and clean the original
Redis epoch. Load the same lifecycle configuration in ordinary/minimal/recovery
modes. The existing launcher remains the final filesystem/activation step; no
binary-promotion framework or new recovery service is needed.
Files: native argument/config boot, SQL connection/reset/guard, offline Redis
maintenance, existing executable SQL journey and docs. Proof: actual binary wrong/
active/legacy refusal, before/after-roster retry, no PID/reward duplication, runtime
exclusion, no world/listeners/filesystem cleanup, SQL-ready then launcher completion,
Redis old-epoch selection and interruption/failure fencing. Matched restore and
other W1–W7 gates remain open; production operation is not authorized.

Implemented `bin/server/dms_new --resume-pwipe EPOCH PORT`: shared verified
connection/guard, full boot metadata/baseline gate, explicit checkpoint-aware
same-epoch reset, and offline old-epoch Redis maintenance. It returns 55 for SQL
readiness (including an already SQL-ready resetting epoch), 58 for refusal/failure;
only the existing launcher can clear files and activate. Legacy pending NULL and
active epochs refuse. No schema extension beyond #334 and no new coordinator or
binary-selection machinery. Common lifecycle config loading also fixes minimal
mode ignoring the configured cap reset/reward preservation policy.

MariaDB 10.11.19: the complete existing native SQL/launcher matrix plus actual
SQL-only process cases passed. The process was SIGKILLed while its roster transaction
slept before checkpoint commit: roster/mappings rolled back, marker stayed 0,
another process was excluded, and retry completed epoch 3 once with configured cap
37. After marker 1, Redis SCAN denial and readiness failure after reward commit
stayed fenced; repair/retry kept PIDs and remaining reward count, cleaned old epoch
26, preserved epoch 27/unrelated keys, and honored preserve=false on a distinct
eligible reset. SQL resume left the file canary; launcher resume removed it and
activated epoch 3. Test setup now uses the canonical sealed migration runner and
opening baselines, so the actual binary's full verifier runs unchanged. Source
contracts now scope the real reset function and recovery's offline drain exception.
The same complete matrix passed on MySQL 8.0.46 with the optimized production
binary. Both engines included real cold-recovery Redis SCAN denial, process
interruption and reward/readiness failure cases. Logs are under ignored
`bin/analysis/pwipe-sql-resume-{mariadb,mysql8}.log`. Optimized binary SHA-256:
`4c5b38d73cbb017e2cc72c8bb3ed1ee183f614fad43b0f70063dfc894df3745c`.
Native malformed/duplicate/missing epoch argument rejection passed; the flat-file
binary refuses SQL-only recovery with exit 58 under valid private configuration.

Development MariaDB, optimized MariaDB production, and isolated flat-file builds
passed. Lifecycle (14), runtime compatibility (7), reset manifest (12), writer/drain,
shutdown/fence/completion/Redis scope contracts and format checks passed. Earlier
five-minute/gameplay/systemd evidence remains applicable to unchanged normal reset,
launcher and writer behavior; full matched restore and final W7 audit remain open.
Format/tidy commit hooks passed; branch and PR are pushed/ready for review. All
private test DB/Redis processes were removed; unrelated local services remain.
Next: qualify a matched pre-wipe SQL/filesystem/Redis backup and restore generation
using the existing backup/restore tools and disposable fixture. Then continue W1
retained custody/baseline consumers and W5 website/donation/client/telemetry cutover;
the website stop still requires its legacy temporary-copy preservation gate. No
release tag or readiness sign-off while those gates remain open.

## Current continuation — durable roster checkpoint

Branch `branch/issue-264-roster-checkpoint`, based on PR #330 at `79593ec9d`.
Review-ready PR #334 (https://github.com/LuminariMUD/Duris/pull/334), implementation
`0d19e6272`; committed and pushed after this handoff update.
Outcome: distinguish an unfinished new reset's roster transaction from one that
already committed, without inferring completion from character data or timestamps.
Add one nullable `roster_recreated` field to the existing season singleton: NULL
preserves legacy/unknown provenance, begin sets 0, and the atomic roster transaction
sets 1. New SQL-ready publication requires 1. This is the dependency for safe
same-epoch SQL-stage recovery, implemented and qualified in PR #336 above.
Non-goals: another job store, new fields on every table, or claiming that existing
SQL/journal backups already cover the filesystem and Redis. Files: additive sealed
migration/verifier and synchronized runtime contract, SQL boundary/roster/readiness,
existing native SQL regression and docs. Proof: both-engine guarded migration,
legacy NULL preservation, transaction rollback/committed marker and readiness
refusal without the checkpoint, focused contracts/builds. Existing SQL-ready legacy
epochs retain filesystem-resume compatibility. Production operations are excluded.
The guarded migration, replay/legacy-value preservation, malformed shape/value
refusal and full sealed runtime contract pass on MariaDB 10.11.19 and MySQL 8.0.46.
The actual native SQL/launcher matrix passes on both engines, including begin=0,
transaction rollback=0, successful roster=1, SQL-ready refusal without 1 and a
post-roster Redis failure retaining 1 while fenced. Legacy SQL-ready NULL filesystem
resume also passes. Both development backends and optimized MariaDB production
builds pass, plus 23 migration-runner tests, seven runtime/boot contracts, 14 lifecycle
tests, 12 reset-manifest checks, writer/quiescence, completion/fence/reward contracts,
format and diff checks. The runtime test's redundant hardcoded migration-head pin
now reads the sealed owner manifest. A MySQL-incompatible constrained-column rename
in an existing corruption fixture now uses the delegated ledger's unconstrained
source-site column, preserving the same missing-schema preflight assertion.

The SQL recovery requirements from this dependency are now implemented and tested
in PR #336 above: runtime exclusion, sealed metadata, same-epoch 0/1 checkpoint
recovery without world startup, committed-roster skip and original Redis epoch.
The existing SQL/journal backup tool still needs verified filesystem/Redis pairing
and recovery rehearsal. Matched restore and full readiness remain open.
Commit hooks passed; PR #334 is ready for review.

## Current continuation — DurisWeb presence fence

Companion worktree `/home/aiwithapex/projects/durisweb-issue264-presence`.
Review-ready DurisWeb PR #93 (https://github.com/LuminariMUD/DurisWeb/pull/93), branch
`branch/issue-264-presence-season-fence` at `34d27ca`, based on master `7147e6b1`.
Review-ready stacked DurisWeb PR #94 (https://github.com/LuminariMUD/DurisWeb/pull/94),
branch `branch/issue-264-presence-diagnostics` at `69c8671`; both branches are pushed
and the companion worktree is clean.
Outcome: prevent cached old-channel messages from being broadcast after the SQL
season boundary. Reuse the current epoch lookup and InnoDB shared row lock through
synchronous publication, ordered against pwipe's existing FOR UPDATE boundary.
Recheck subscriber identity/channel and in-memory hook state after async work.
Non-goals: another epoch store/cache, frontend protocol changes, new MUD writes,
or deployment. Files: website subscriber, focused behavioral/native lock tests,
architecture note and local release-note draft; keep this server plan updated.
Proof: enabled/disabled delivery, resetting/changed/missing epoch and DB failures,
stop/refresh/hook races, rollback/connection ownership, real SQL boundary ordering,
and required backend checks. Focused unit/hook/security suites pass (78 tests;
the opt-in native case is separately run). Native SELECT-only lock ordering passes
on MariaDB 10.11 and MySQL 8.0: the MUD FOR UPDATE selector times out while publication
holds its shared lock, then succeeds after commit; fenced old events are refused and
a fresh subscription receives epoch 2. Backend format/lint/type/build and the 53-write
MUD allowlist audit pass. No lockfile/dependency changes were needed (offline cache
reuse). Local admin Website Changelog draft is prepared; publication waits for
verified deployment. A separate diagnostics finding was fixed in this subscriber:
startup/refresh/Redis/close callbacks previously forwarded raw driver messages. Four sentinel
cases reproduced the disclosure; PR #94 replaces those details with fixed categories.
All 82 focused tests and required backend checks pass. Native lock evidence from
PR #93 is reused for this diagnostics-only follow-up. No extra public news entry
is needed for internal log text. The admin draft is local/unpublished; no deployment
or live application write occurred.

Next: backup/recovery prerequisites and matched restore/SQL-stage recovery using
`src/sql/sql.c`, `scripts/persistence_backup.py`, `scripts/persistence_restore.py`
and existing disposable fixtures. Native SQL-stage resume is now qualified in
PR #336 above; use its guarded entry point, never manually set active as recovery.
W5 also retains whole website/cache/donation/client/telemetry cutover acceptance.
Before any website service stop, follow its `docs/deployment.md` legacy temporary-copy
preservation gate: PrivateTmp cleanup can remove unmanaged copies. Rehearse that
external-writer cutover with synthetic data; the source fence alone is not the full
website integration journey.

## Redis dependency failure qualification

Branch `branch/issue-264-redis-failure-qualification`, based on PR #327 at `f1db24d4d`.
Review-ready PR #329 (https://github.com/LuminariMUD/Duris/pull/329), implementation
`4c2017f15`; committed and pushed.
Outcome: exercise actual SQL reset orchestration with the real Redis maintenance
provider against disposable endpoints. Non-goals: changing game behavior, a second
Redis client implementation, or activating incomplete SQL after cache repair.
Files: existing native SQL/launcher journey and this handoff. Proof: unavailable
endpoint preserves old SQL/Redis state before the boundary; a real SCAN-denying ACL
fails after the boundary and leaves epoch 27 fenced; repaired repeated cleanup
preserves unrelated keys and does not activate SQL. The complete native matrix,
existing live Redis maintenance test and both Redis surface contracts passed.
The complete real service/Redis journey is qualified separately below.

## Current continuation — Redis-on and systemd runtime journey

Branch `branch/issue-264-systemd-qualification`, based on PR #329 at `4c2017f15`.
Review-ready PR #330 (https://github.com/LuminariMUD/Duris/pull/330), implementation
`f3768e7cf`; committed and pushed after this handoff update.
Outcome: real five-minute reset with private Redis and the complete systemd sandbox/
restart settings, followed by staff access and fresh gameplay/save/reconnect/reboot.
Reuse the existing runtime journey and production-profile binary; no game or launcher
behavior changes. The uniquely named private service uses the production template
with test identity/path/description, local configuration and `--minimal`; all sandbox/
restart settings stay intact. An active After reference retains its exit statistics
without starting or restarting it. Non-goals: production deployment, another runtime
framework, or repeating valid Redis-off qualification. Files: existing journey and
runbook/regression/plan.

**Proof passed:** actual exit 58 stayed fenced without restart; the real countdown
and SQL -> Redis -> exit 55 -> filesystem -> epoch-2 activation completed, and exit
55 also stayed stopped. Old scoped/legacy Redis sentinels disappeared; unrelated
namespaces survived. Recreated Overlord PID 2 could login/save, remained absent from
public presence under existing wizard-invisibility policy, and a visible fresh
mortal PID 3 published in epoch 2, fought/looted/saved/reconnected and survived another
boot. Retired PID 1 stayed inactive. All fixture units/processes were cleaned up.

Artifact: `bin/analysis/pwipe-runtime-mariadb-redis-systemd.json`, status `passed`;
core source `f1db24d4d` with an empty source diff; binary SHA256
`e10133dd69aaf1da8cb16b8585e8b750e9c8428a7b5775b30d9a7ff4d37a7033`.
Wall countdown/reset observation: **303.049 seconds**, monotonic **292.201 seconds**;
the game uses wall time and both clocks are recorded. Service results: exit 58,
failed, zero restarts; exit 55, inactive/success, zero restarts. Existing three-build
and Redis-off gameplay evidence is reused: this chunk changes only tests/docs.
Commit hooks passed; PR #330 is ready for review. Scope is the private mini world; full #264 readiness remains
open for inventory/custody/recovery, Redis re-enable, external cutover and the other
W1–W7 acceptance items.

The source-confirmed DurisWeb stale-event finding at `7147e6b1` is addressed by
companion PRs #93/#94 above. Their native shared-row-lock proof is local and backend
scoped. Other website readers/writers, queued donations, cached lists, reconnecting
clients and telemetry attribution still need the W5 cutover rehearsal.

## Current continuation — flat-file command rejection

Branch `branch/issue-264-flatfile-rejection`, based on payload PR #326 at `e332d12b5`.
Review-ready PR #327 (https://github.com/LuminariMUD/Duris/pull/327), implementation
`5dd0a44c8`; committed and pushed after this handoff update.
Outcome: reject unsupported flatfile-primary pwipe before scheduling a countdown or
changing an existing shutdown. Current code schedules five minutes and only then
fails in the SQL stub. Use the existing persistence-mode predicate at command entry.
Non-goals: adding flat-file wipe support or weakening MariaDB qualification.
Files: shutdown command, existing pwipe runtime journey, runbook/regression/plan.
Proof: real flat-file authority on the supported client-free build; preserved player snapshot
and legacy sentinels, no countdown/cleanup, normal save/logout/reconnect/second boot.
Reuse private world/account and offline Overlord-promotion helpers. Source inspection
confirmed hybrid fallback mode is already rejected by `persistence_mode_configure()`;
a direct test also confirmed the MariaDB binary rejects flatfile-primary at startup.
There is no supported hybrid fallback wipe to implement or qualify.
The actual flat-file journey passed immediate/malformed-form rejection, unchanged
player snapshot and legacy file sentinel, preserved scheduled reboot, and normal
save/logout/reconnect/second boot. Artifact `bin/analysis/pwipe-runtime-flatfile.json`
records binary SHA256 `3482bd15b6df6c400db6b0523f3112357ac1de2e7bbcf5c67e5f620cb58ecd42`
and the source diff digest at qualification. Both development builds, optimized
MariaDB production build, formatting and reset-fence contracts passed. Commit hooks
passed; PR #327 is ready for review. Full readiness remains open. Next: extend the existing MariaDB runtime journey
with private Redis and, if practical, the full systemd sandbox in one five-minute
run. The production restart properties were already tested in isolation; the real
service should use a private mini-world and test-only unit name, never the live unit.

## Current continuation — remaining live payload stores

Branch `branch/issue-264-payload-reset`, based on cargo PR #325 at `d92559fdb`.
Review-ready PR #326 (https://github.com/LuminariMUD/Duris/pull/326), implementation
`b2790e7cf`; committed and pushed after this handoff update.
Outcome: clear `auction_item_custody` and siege items/affects/descriptions with the
other seasonal physical payloads. The actual boot population readers scan these
stores; old rows must not remain new-season presence or uncertainty evidence.
Non-goals: deleting auction/item ledgers, receipts, reconciliation quarantine, or
inventing season columns. Keep quest trophy history: the only current SQL boot read
fills an unused cache; both old quest-trophy gameplay calls are commented out.
Files: SQL preflight/reset/postflight, canonical manifest, existing native journey
and reset-order checks, runbook/regression/plan. Proof: populated custody/siege
rows and children, actual reset, empty real boot reader output, missing-schema
preflight and failed cleanup fencing. The complete native SQL/launcher matrix passed,
including positive raw boot reader output before reset and empty output afterward,
FK-linked nested siege items/affects/descriptions, a missing child table abort before
epoch advance, and a triggered delete failure that never publishes SQL-ready.
MariaDB/flat-file development and optimized MariaDB production builds passed;
12 manifest checks (21 dependency-order assertions), 14 lifecycle tests and the
reset-fence contract passed. Commit hooks passed; PR #326 is ready for review.
Full readiness remains open. Next: qualify the unsupported flat-file command path
on the actual built server, then Redis-on and service/recovery gates.

## Current continuation — prepared cargo replay proof

Branch `branch/issue-264-cargo-replay`, based on artifact PR #324 at `75367cc07`.
Review-ready PR #325 (https://github.com/LuminariMUD/Duris/pull/325), implementation
`205e7bbbf`; the worktree is clean and pushed after this handoff update.
Outcome: prove retained cargo books/receipts and a pre-reset prepared trade cannot
restore wiped wallets, ships, cargo or markets, including a fresh same-named mortal
and new ship. Use the actual policy, command codec, SQL executor and receipt path.
Non-goals: a generic epoch field/cutoff or altering protected receipts without a
reproduced need. Files: extend the existing native SQL journey and its regression/
runbook/plan references. Proof: one committed and one unapplied prepared purchase,
actual reset, receipt replay and stale-command rejection before/after fresh identity
creation, unchanged historical book/generation and zero restored after-images.
The complete real native SQL/launcher matrix passed: receipt replay was inert,
prepared execution returned ESTALE before and after a same-named fresh mortal/new
higher-ID ship, and the normal critical repository refused the pending command.
Both old/new wallets, retained books/generation, and deleted cargo/market tables
remained unchanged. No source behavior change, new epoch field or generic cutoff
was needed. Existing build and five-minute gameplay evidence is reused for this
test/documentation-only chunk. Commit hooks passed and PR #325 is ready for review;
full readiness remains open.

Next W1 retained payload consumers: `auction_item_custody` (pickup reads plus
artifact population scanning), and `siege_items`/children (artifact population
scanning). Trace active versus immutable historical use before changing retention.
General custody/baseline boot behavior, SQL-stage recovery/restore, Redis-on/external
cutover, flat-file command rejection and full service qualification also remain.

## Current continuation — artifact retirement

Branch `branch/issue-264-artifact-reset`, based on collector PR #323 at `025a6da7c`.
Review-ready PR #324 (https://github.com/LuminariMUD/Duris/pull/324), implementation
`527a3cafb`; committed and pushed after this handoff update.
Outcome: clear current artifact ownership, timers and souls while retaining retired
canonical UIDs, rejected UIDs, delivery markers and immutable history. Reuse the
existing retired/absent identity states so both runtime and SQL delivery recovery
recognize old bodies as retired and new bodies may spawn. Keep ledger revisions and
baseline history unchanged: current repository revisions derive from the greatest
ledger/baseline revision; historical outcomes do not replay gameplay snapshots.
Non-goals: deleting audit/baselines, new schema, or a second artifact lifecycle.
Files: SQL reset/manifest, existing native SQL and artifact boot tests, runbook/plan,
and the existing reconciliation check (domain-only retired rows are valid history).
Proof: seeded owned/retired/unresolved records, actual reset and boot/population/new
creation, old pending-delivery and receipt replay, retained history/revision, and
failed-update fencing. The full native SQL/launcher matrix passed, including the
actual boot/population/creation/save/reload executable and old pending delivery/
receipt replay. All existing artifact snapshot cases passed under UBSan. The
reconciliation tool now accepts cleared domain-only identity history and returned
zero for all checks against the reset DB; baseline and ledger rows were unchanged.
MariaDB and flat-file development builds, optimized MariaDB production build,
12 season-manifest and 14 lifecycle checks and reset-fence contracts passed.
Commit hooks passed; PR #324 is ready for review. Full readiness stays open.
Next concrete consumer: prepared cargo commands in `divine_trade_repository.c`
validate market generation/book state, player wallet/account and ship owner/preimage.
Ships and players have monotonic IDs, so prove stale prepared commands reject after
reset before adding epoch/cutoff machinery. Ordinary critical outbox receipts do not
replay wallets; `comm.c` documents that the old journal directory now holds only
locker identification receipts. Trace actual consumers, not historical names.

## Current continuation — collector retirement and recovery view

Branch `branch/issue-264-collector-reset`, based on PR #322 at `297045583`.
Review-ready PR #323 (https://github.com/LuminariMUD/Duris/pull/323), implementation
`b0b7206c0`; all changes are committed and pushed after this handoff update.
Outcome: use existing `collector::reason::season_reset` cancellations through the
normal audited critical repository. Candidates close; held stock moves to destroyed
custody; record blobs, payloads, receipts and listing-ID allocation survive. Derive
operation identity from reset epoch/listing. Preflight validates pending records and
held payload/custody after writer drain, before advancing the epoch. Reset then
commits each normal command; retry skips already-terminal rows. Normal bootstrap
must omit terminal history whose beneficiary is retired, so protected old receipts
do not consume the new season's bounded catalog. The reset scan needs pending rows
across all owners, including deleted beneficiaries. Reuse the existing bootstrap,
codec and command executor; no new store, binary offsets or un-audited status patch.
Files: SQL orchestration, collector bootstrap query/header, existing native DB tests,
manifest and runbook/plan. Proof: real candidate/held/paused records, destruction
ledger, restart view, receipt/payload/ID retention, stale purchase refusal and failure/
retry fencing. Positive native cases and the existing full SQL collector suite
passed; the final matrix now includes real pre-reset purchase rejection, new-owner
bootstrap, corrupt payload, delegated schema loss and partial cancellation/retry.
Preflight reuses the existing runtime metadata fingerprint rather than duplicating
all delegated writer column lists. The complete native matrix and existing SQL collector
suite passed, together with the real writer/quiescence harness, reset-fence/reward
contracts, 12 season-manifest and 14 lifecycle checks. MariaDB and flat-file development
builds and the optimized MariaDB production build passed. Final review confirmed the
authoritative cache accepts an equal-revision refresh when retired history disappears;
no extra revision mechanism is needed. The final native matrix and incremental
MariaDB build passed after review; formatting/tidy hooks passed. Full readiness
remains open. Next: artifact current ownership and compatible reconciliation baselines;
`src/guild/artifact.c` loads `artifact_domain_state` unscoped after the old legacy
rows have been wiped. Inspect its history/recovery consumers before choosing reset
semantics; retain immutable history and monotonic identity/revision allocation.

## Current continuation — retire active Divine Boons

Branch `branch/issue-264-divine-reset`, stacked on kingdom PR #321 at `2640ae94d`
(https://github.com/LuminariMUD/Duris/pull/321), review-ready.
Published as PR #322 (https://github.com/LuminariMUD/Duris/pull/322), implementation
`af12278b2`; current worktree is clean and pushed after this handoff update.
Outcome: retire old active objectives and selection-repeat preferences in one
versioned state transition, while preserving monotonic boon IDs, staff recent history,
mode/pause configuration and protected cargo-book identities. Reuse the existing
model serializer/repository CAS; no new schema or blanket ledger deletion. Validate
the existing snapshot before crossing the reset boundary. Files: existing boon model/
repository, SQL/manifest, native model/DB tests and docs. Proof: seeded active EXP and
cargo slots, empty post-reset slots/history, retained IDs/audit/config, idempotent
repeat, corrupt-state preflight and failed durable update fencing. The ASan/UBSan model
test and actual SQL/native matrix passed, including a database-triggered failed
update followed by one repaired retirement. Both development backends and the
optimized MariaDB production build passed, as did all 12 season-manifest checks,
14 lifecycle tests, reward/SQL contracts and diff checks. Commit hooks passed
and PR #322 is ready for review; earlier five-minute evidence is reused for unchanged
reset paths. No readiness sign-off, merge, release tag or deployment is claimed.

Next retained-state consumers to trace after collector PR #323: artifact current ownership/baselines in
`src/guild/artifact.c` and prepared cargo replay in
`src/economy/divine_trade_repository.c`. Old financial commands must not restore
wiped cargo/market/player after-images. Preserve audit/receipt evidence and prove
actual startup/recovery behavior before closing those W1/W2/W4 items. SQL-stage
resume/restore, Redis-on/external cutover, flat-file rejection and full system-service
qualification also remain. Do not sign off readiness from the completed chunks.

## Kingdom reset delivery

Branch `branch/issue-264-kingdom-reset`, stacked on reward retry PR #318 at
`b35af6d08` (https://github.com/LuminariMUD/Duris/pull/318), review-ready.
Outcome: remove realm resources/territory, purchased garrisons and legacy land before
removing their association owners. Those association IDs are reused; current SQL
loads are unscoped by season. Add the three real stores to preflight, postflight and
the existing lifecycle classifications. Non-goals: new schema, realm mechanics,
protected historical ledgers or another reset manifest. Files: SQL, manifest,
existing native SQL journey, runbook/plan. Proof: seed real positive world rows,
execute the actual reset, reuse an association ID and prove no holdings/guards;
missing-store preflight must preserve the old epoch. The actual SQL journey passed
positive territory/resource/guard deletion, association-ID reuse and missing-store
preflight; both builds passed. It exposed another stale source-test schema list,
now replaced with the same sealed migration inventory already used by the lifecycle
validator. All 12 reset-manifest and 14 lifecycle checks, both builds, and hooks
passed before publishing PR #321.

## Reward retry delivery

Branch `branch/issue-264-reward-retries`, based on PR #317 at `7fc360575`.
Outcome: bind reward-policy eligibility and its committed stamp to the fixed SQL
reset start and validate the current resetting epoch. Preserve the 28-day business
protection between distinct resets, while making same-reset retries safe even
months later. Clear old summon/body links regardless of that protection window.
Files: existing account reward hook/config, native DB harness, regression docs/plan.
Proof: real hook on the private migrated DB, both preserve modes, expiry/finite and
permanent grants, same/distinct reset timing, rollback and lost-ACK retries; focused
builds/contracts. Non-goals: new schema, ledger or migration framework, and changing
approved grant rates/lifetimes. Existing singleton + policy timestamp suffice.
The real hook/private-DB matrix passed, including invalid boundaries, delayed
retries, fixed-boundary 28-day protection, both configurations, rollback and lost
ACK. Both backend builds and the exact reward source contract passed; format/hooks
and publication passed. Published as PR #318 at `b35af6d08`. Full readiness remains open.

## Implementation handoff — 2026-10-24

- Reused `/home/aiwithapex/projects/duris-issue264-plan`, clean at `1ec58eee5`;
  merged current master `7d3bd3b95` as `3031b0fef` without rewriting history.
  Merge hooks passed changed-line format and tidy. Preserved current master’s
  Divine Boons plan in `plan-issue-245.md`; this document remains the #264 plan.
- First focused dependency: remove the validator/test's duplicate hand-maintained
  schema lists. Reuse the migration runner's sealed, ordered manifest plus the
  two supported bootstrap sources. This covers 200 SQL tables on this revision,
  including recent Divine trade state; no reset behavior or retention policy changes.
  Found and repaired phantom foreign-key dependencies from tables dropped by later
  supported migrations; the complete sequence exposed this validator crash.
  Proof: `python3 tests/async/test_data_lifecycle_manifest.py` (14 passed),
  `python3 scripts/validate_data_lifecycle.py` (200 SQL tables, 30 other stores,
  42 Redis surfaces). No C/C++ change: no server rebuild needed.
- The wider migration-runner check exposed an existing test tied to “last migration”
  instead of its reviewed manifest prefix. Corrected that test separately, matching
  the other reviewed-online-migration fixtures; all 23 runner tests passed.
- PR #309: https://github.com/LuminariMUD/Duris/pull/309, review-ready at `470c9c92a`.
- Current chunk: W3 SQL-to-launcher completion/failure contract, including fenced
  post-boundary failures, durable SQL-ready state and guarded filesystem completion.
  W2 writer drain and W4 completeness/carryovers remain required before runtime
  readiness. No production actions, readiness sign-off or release tag.
- The baseline list failures were repaired on master before this continuation;
  removing the remaining duplication prevents the same drift recurring.

### SQL/filesystem handoff chunk (stacked after PR #309)

Outcome: keep boot fenced through filesystem deletion and distinguish failed stops
from deletion permission. Files: existing SQL/comm/launcher/wiper/service paths,
runbook, regression index and focused handoff tests. Non-goals for this chunk:
writer-drain/completeness/carryover policy repairs, full gameplay and deployment.
Those remain required for the overall issue. Ablation removed a proposed migration:
existing status + completion timestamp already encode the SQL-ready handoff.

- `resetting`/NULL completion: SQL incomplete, no file cleanup permitted.
  `resetting`/timestamp: SQL/Redis/rewards ready, filesystem still fenced.
  `active`/timestamp: full handoff complete. Launcher final activation is guarded
  by epoch; duplicate completion never deletes newly created files.
- Exit 55 requires acknowledged SQL readiness; 58 stops incomplete resets.
  Launcher additionally checks the boot epoch's successor before cleanup and
  preserves both statuses. Production unit prevents automatic restart for both.
- Filesystem preflight validates every fixed legacy target before deletion and
  is invoked before SQL's irreversible boundary; cleanup revalidates. SQL reward
  failure now prevents SQL-ready publication. SQL-stage resume is still unimplemented;
  matched restore is the documented safe recovery route for that stage.
- Proven: 4 executable filesystem/launcher-contract tests; SQL completion, durable
  fence, existing quiescence/source-manifest and both Redis source contracts passed.
  `run_pwipe_handoff_mysql.py` applied the sealed sequence on a private MariaDB 10.11,
  matched all 200 actual tables, executed native begin/ready/boot-fence functions,
  and passed real launcher resume/failure/retry/lost-ACK cases. This is a handoff
  journey, not the full command-to-fresh-gameplay acceptance journey.
- Both builds passed: `make -C src -j4 PERSISTENCE_BACKEND=mariadb` and
  `make -C src -j4 PERSISTENCE_BACKEND=flatfile BIN_ROOT=$PWD/bin/qualification-flatfile`.
  `format.sh --check`, shell syntax,
  runtime compatibility validation and `git diff --check` passed.
- Executed the exact production restart properties in isolated user-systemd transient
  services: after 12 seconds, exits 55 and 58 had one invocation each; reboot exit 52
  had two. All fixture units stopped/reset afterward. This proves restart policy,
  not the full installed system-service sandbox.
- Remaining W3 proof: actual server exit/handoff in W6, interruption at the process
  boundary, full installed service sandbox and SQL-stage recovery. W2, W4, W5 and
  the fresh-gameplay journey remain open. Do not sign off #264 or #97.

- Follow-up on PR #311: the normal `sql_clear_zone_trophy()` queues on the writer.
  Pwipe must perform its own zone reset through the main SQL connection after the
  gate closes. Replaced that call and extended the private DB harness to compile
  and execute the actual full `sql_pwipe()` and its schema pre/postflight. That
  executable passed with the real MariaDB schema and zone reset assertions; both
  backend incremental rebuilds passed. This remains a controlled-peripheral SQL
  journey, not the real game command journey.

### Writer-quiescence chunk (stacked after PR #310)

PR #310: https://github.com/LuminariMUD/Duris/pull/310 at `3224c38d1`, ready for review.
Current outcome: drain accepted coordinator/outbox/maintenance/player/locker/artifact
work before SQL's boundary, then close the actual shared writer's admission gate.
Reuse existing drains; add only reversible quiesce/resume at the one writer because
player-pipeline quiescence alone does not cover SQL, banks and world-save jobs.
Pre-boundary failure resumes existing workers; an ambiguous boundary never resumes.
Suppress post-reset kingdom writeback and the remaining old-world pulse, and join
the drained writer on pwipe exit. Full W2 is still open for external/direct writers
and startup recovery isolation; W4/W5/W6 are still required.

- Found a concrete outbox defect: quiesce only changed health, while its background
  loop continued polling. Quiesced workers now poll only to satisfy an explicit
  drain; game-thread preparation closes admission again after publication callbacks.
- Proof: real shared-writer held/callback/late-refusal/abort-resume and accepted-write
  failure tests pass; existing worker and coordinator suites pass, as do copyover
  guards and durable-boundary checks. Both final backend incremental builds passed.
  `bash tests/async/run_critical_command_schema_mysql.sh` passed on private MySQL 8,
  including actual pause/drain/resume and the existing 60-second audit cadence case.
  Source modified time precedes the executed outbox binary; no repeated full suite
  is needed for unchanged outbox code. Required format/tidy hooks run at commit.
- Owner decision, 2026-10-24: **reset all account-bank balances; recreate only
  level-62 staff (Overlords)**. All other characters are wiped, including staff below
  62. Preserve the associated accounts; recreation must not restore seasonal items,
  money, progression or ownership. Implemented in #312/#313 and exercised through
  real login/gameplay in #317; historical notes below describe that delivery.
- No production operations.

### Seasonal bank reset chunk (stacked after PR #311)

PR #311: https://github.com/LuminariMUD/Duris/pull/311 at `2f123996e`, review-ready.
Owner explicitly confirmed all bank balances reset and only level-62 Overlords are
recreated. This chunk deletes every `account_banks` row, adds it to reset preflight
and postflight, and corrects its existing lifecycle classification. Accounts,
credentials/donations, historical currency baselines/ledger and monotonic bank IDs
survive. A recreated bank gets a new ID and zero initial balances, so old baseline
identity is never reused. No schema migration, account deletion, history purge or
new reconciliation framework is needed. Exact Overlord recreation and persistent
old-operation replay isolation remain next work; this is not full W4 completion.
Proof: `python3 tests/async/run_pwipe_handoff_mysql.py` passed the actual full
SQL reset with nonzero banks on Good/Evil/neutral, unchanged account credentials
and donation history, retained old baseline, fresh bank ID and zero defaults.
All 14 lifecycle and 12 season-manifest checks passed, as did the standalone
validator (200/30/42), both backend incremental builds and `git diff --check`.
No production operations.

### Exact level-62 Overlord recreation (stacked after PR #312)

PR #312: https://github.com/LuminariMUD/Duris/pull/312 at `d8919da5f`, review-ready.
Outcome: recreate only current exact level-62 staff under the same accounts/names,
with new monotonic PIDs and clean progression/assets. In one transaction snapshot
only their identity/physical template, retire all old rows under reserved `~pwipe-PID`
names, insert clean staff and opening baselines, and restore only those account links.
Retired SQL history stays inactive; names become available without reusing ledger IDs.
Clear old summon-to-body links independently of the 28-day grant-decrement guard.
No durable table/framework or old inventory/preferences copy is needed. Files: SQL,
existing native DB journey/source contract and runbook. Proof: extend the actual SQL
journey with levels 56/61/62/63, new identity/baseline/zero assets/name reuse; full login
proof and replay isolation still belong to W6/W4. The native SQL journey passed
exact-level selection, clean fresh identities/baselines, account mapping and mortal
name reuse; an injected mid-recreation SQL failure rolled back the entire roster
and left the SQL fence in place. Both backend builds and focused source/lifecycle
checks passed (14 lifecycle tests, 12 manifest checks plus SQL/fence/writer tests).
The final test extension removed a required recreation column and proved a
pre-boundary refusal with unchanged epoch; it and commit hooks passed before #313
was published.

### Runtime qualification continuation

PR #313: https://github.com/LuminariMUD/Duris/pull/313 at `427860b58`, review-ready.
Current branch: `branch/issue-264-runtime-qualification`, based on that stack.
Published as PR #317: https://github.com/LuminariMUD/Duris/pull/317 at `e8b43d01c`.
PRs #309, #310, #311, #312, #313, #316 and #317 are review-ready and unmerged.
`tests/async/run_pwipe_runtime_journey.py` was published and passed using a private
MariaDB via the existing wrapper, supported adopt/run migrations, copied real launcher
and binary, synthetic world/account, real five-minute pwipe, explicit next boot,
recreated staff login and fresh mortal combat/save/reconnect/reboot. It uses no
checkout `.env`; mail/Discord/telemetry are absent/disabled. Extends the existing
creation fixture only to log into the preserved account before creating a mortal.
First real execution passed mortal denial, malformed/cancelled requests and actual
countdown -> exit 55 -> filesystem cleanup -> active epoch 2. The test then failed
its timing assertion because it started measurement after buffered notice output;
start time now precedes command send. A second run again completed activation but
showed the same ~293-second monotonic measurement; collect wall-clock duration
against the actual calendar-based shutdown deadline in the next run. Do not call
the discrepancy solved or weaken the real configured five-minute countdown.
A 10-second host probe measured 10.884 seconds of wall time versus 10.000 seconds
of monotonic time; the clocks drift here. The game uses a calendar deadline, so
record both durations and assert the wall-clock interval. GDB read-only inspection
of the disposable server confirmed its stored deadline (no timer acceleration).
Source review found the game SIGCHLD handler can reap the preflight child first;
reuse `take_reaped_child_status()` on ECHILD. The native handoff test now forces
that real reaper ordering. The successful scoped result is recorded below. Outputs remain
uncommitted under `bin/analysis`.

Consumer review during countdown: `zone_story_quest_runtime.c` already derives
`current_season_id()` from the SQL epoch and passes it to rendering, assignments,
transactions and character registration. Existing `test_zone_story_quest_feature.py`
passed; preserve the season-keyed history. Kingdom ownership has no such epoch gate:
`kingdom_realms` is loaded by association ID (which can be reused), with garrison/land
side state; it must reset. Divine Boons' `next_id` must remain monotonic if active
slots are expired at cutover, to avoid reusing retained cargo-book boon identities.
Do not blanket-delete protected ledgers; trace live consumers and reset current views.

Independent production-build finding: `ship_shop_proc` maintained `owned` separately
from `ship`, causing an optimized `-Werror=null-dereference` failure. Isolated minimal
repair is review-ready as PR #316 at `ee152d2ba`, in
`/home/aiwithapex/projects/duris-issue264-ship-build` on
`branch/fix-ship-shop-production-ownership`. Full MariaDB production build and the
native ship-panel/staff-cargo guards passed there. Incorporate that commit into the
qualification stack before executing the full production-unit fixture. No production
service or user worktree was changed. Production repair was merged into the qualification branch as `f6694e7fe` and
the combined production build passed. Runtime changes are published in #317.

Next focused implementation candidates after runtime publication:

- Reward retry accounting: current guard compares `last_processed_at` to retry-time
  `NOW()`, so an old unfinished reset retried after 28 days can consume again.
  Evaluate the existing durable `reset_started_at`/epoch instead: base eligibility
  on that fixed boundary and stamp it atomically with grant policy. This may meet
  exact retry accounting without a new migration/ledger. Prove same reset after
  >28 days, distinct resets inside/outside the business guard, both preserve modes,
  grant expiry, summon clearing and lost COMMIT acknowledgment before choosing it.
- W5 companion source rechecked at DurisWeb `7147e6b1`: active-season presence/cache
  reads already query the SQL fence, but failed 60-second subscriber refresh retains
  its previous channel. The manual workflow must stop external seasonal writers
  before reset and restart them only after activation; exercise it and fix stale
  event handling independently if needed. No DurisWeb edits or operations yet.

Runtime result: **PASS**, MariaDB-primary with Redis disabled, using the real
five-minute command (300.581 wall seconds; 292.483 monotonic on this drifting host).
Mortal denial, malformed confirmation, cancellation, old-season observations,
actual exit 55, full SQL/launcher/filesystem cleanup, epoch 2 activation, existing
account + recreated level-62 login, fresh mortal combat/loot/save, reconnect and
another boot all passed. Old PID 1 stayed inactive; fresh staff PID 2 and mortal
PID 3 persisted. Old pfile/ship sentinels disappeared and backup sentinel survived.
Evidence: `bin/analysis/pwipe-runtime-mariadb.json` (uncommitted), binary SHA-256
`69adaed05e55b82e5b2a0f44ae47fb4570e89757fa5a451eca95bdc981b4830b`, source
`427860b58` plus the reaper repair. Later ship ownership repair was independently
qualified and merged as `f6694e7fe`; no repeated five-minute campaign for that
unchanged reset path. Required `format.sh --all --check` passed all 1,147 C/C++ files;
MariaDB development, isolated flat-file and the full combined MariaDB production
builds passed. Forced actual reaper/SQL/launcher failure tests and affected source
contracts passed. This proves the mini-world, Redis-off path, not full wipe readiness.

Remaining blocking work is still W1's complete consumer inventory, W2 direct/external
writers/replay, W4 active retained stores and epoch-bound reward retries, W5 website/
Redis/telemetry cutover, and W6 failure/recovery/full installed service evidence.
The finished PRs do not sign off the wipe. Continue autonomous local qualification.

## What the code currently does

These are baseline observations, not claims that every failure has been reproduced.

1. **Permission and confirmation exist.** `do_shutdown()` in `src/cmd/actwiz.c`
   accepts `shutdown pwipe confirm yes` only at `OVERLORD` and schedules five
   minutes. A later shutdown command cancels the pending request. Help says leaving
   the game cancels a schedule, but `timedShutdown()` has that cancellation block
   commented out. Test command-table access, malformed input, cancellation,
   notices and issuer disconnect; resolve the help/behavior mismatch deliberately.
2. **A durable SQL fence exists.** `sql_begin_pwipe_epoch()` locks the singleton,
   increments its epoch, and records `resetting` before reset SQL. Ambiguous COMMIT
   sets `pwipe_crossed_boundary`. Startup's `sql_load_active_season_state()` refuses
   a non-active season. Reuse this fence.
3. **Completion is premature across processes.** `sql_pwipe()` calls
   `sql_complete_pwipe_epoch()` and emits `WIPE COMPLETED!` before server exit and
   filesystem cleanup. A filesystem failure therefore has no remaining SQL fence.
   Post-boundary SQL failure also leaves `_pwipe` set; `src/net/comm.c` returns 55
   for it just as for SQL success. The launcher treats either 55 as permission to
   wipe files and can print `Wiped!` after incomplete SQL reset. This is a concrete
   control-flow defect, not merely a missing test.
4. **Launcher stopping is not service stopping.** The loop treats 55 as terminal,
   requires executable `wipe_it_all`, and exits nonzero on filesystem error. The
   production unit nevertheless has `Restart=always` and no pwipe-specific restart
   prevention. The runbook's 55/no-restart statement does not describe the entire
   installed service. Qualify both direct-launch and service modes.
5. **Skipping shutdown saves is not writer quiescence.** `_pwipe` suppresses
   terminal saves/extraction, dirty marks and several world saves. Reset SQL runs
   inside `timedShutdown()` before game-loop shutdown quiesces the coordinator/
   outbox. `critical_command_coordinator.c` explicitly notes that an already queued
   job still lands after coordinator shutdown. `player_save_pipeline.h` already
   provides quiesce/resume/drain/finish operations. `kingdom_shutdown()` retries
   upkeep and flushes dirty realms when enabled, and runs after the game loop
   during pwipe too. Inventory all writers and demonstrate races with held jobs;
   a flag alone is not proof of safety.
6. **Inventory classifications need consumer review.** The lifecycle manifest
   classifies 199 SQL tables and 24 other stores. It retains recovery evidence and
   active stores such as `item_current_owner`, `collector_listings`, `kingdom_realms`,
   `kingdom_garrison`, `zone_story_quest_state` and `divine_boon_state`. Kingdom loads,
   collector repositories, player-load ownership joins and quest/boon loads consume
   them. Retaining bytes and letting them influence a new season are separate
   decisions. Trace consumers before deleting, deactivating, reinitializing or
   retaining with isolation.
7. **Filesystem cleanup is a legacy allowlist.** `wipe_it_all` clears letter
   buckets/named stores under `Players/`, `Ships/` and optional root `Corpses/`,
   preserving `Players/Backup`. It does not cover every manifest store. Modern
   flat-file authority uses `FLATFILE_STATE_DIR`; `sql_pwipe()` under
   `__NO_MYSQL__` returns false. The script is not a complete flat-file backend wipe.
8. **Rewards have policy but lack reset identity.**
   `account_bound_rewards_on_successful_pwipe()` uses a transaction and global
   `last_processed_at` with a documented 28-day guard (`lib/account_rewards.cfg`).
   `pwipe.preserve=true` keeps permanent/unexpired grants, decrements finite grants,
   expires exhausted grants, and clears summons on a processed wipe; false removes
   grants. Failure is logged but SQL still declares completion. A timestamp window
   does not identify a reset. Preserve the documented 28-day business protection
   unless explicitly changed; separate it from retry accounting.
9. **Redis is already season scoped.** `redis.c` captures SQL epoch once at boot.
   Cleanup cancels donation/presence/cache/legacy-ship work, quiesces world recovery,
   and deletes/verifies old-epoch keys through `redis_maintenance.c`. Disabled Redis
   skips cleanup; later activation must still ignore old epochs. Reuse isolated
   Redis tests. Check legacy unscoped cleanup against shared installations; do not
   introduce `FLUSHALL` or another namespace scheme.
10. **Telemetry season is independent configuration.** `telemetry_runtime.c` loads
    `TELEMETRY_SEASON_ID` (default 1), independently of SQL epoch. PostHog identities
    include environment/season; the outage ledger preserves quota reservations and
    sender ownership. Specify cutover without deleting history, resetting same-day
    project quota or relabeling old events.
11. **Website epoch consumers exist.** Read-only inspection of local DurisWeb
    revision `7147e6b1bece2e650dbe3cb312c904edfa43bf9d` found active-season queries in
    `backend/src/services/onlinePlayersService.ts`, `playerEventSubscriber.ts` and
    `donationOutboxService.ts`. The subscriber refreshes every 60 seconds; failed
    refresh can leave its prior subscription in place. Test stale events, response
    caches, websockets, donations and leaderboards. This is source evidence, not
    deployed validation. Recheck its revision and link companion fixes to #264.

## Implementation work items

### W1 — Reset/preservation contract and fixture (4–6 hours)

- [ ] Inventory tables from the supported migration runner's applied manifest and
  a fully migrated disposable DB, not a glob of historical SQL. Compare lifecycle
  classification and runtime pre/postflight, foreign keys, retained parents,
  identities/sequences and inactive account-character semantics. Include newly
  landed systems at the final qualification revision.
- [ ] Inventory paths from readers/writers, Redis registry keys/channels, workers,
  maintenance jobs, website writes, telemetry and backup/restore tools. Record each
  store's authority, readers/writers, reset/retain action, recovery behavior and
  assertion in the existing manifest/runbook. Archives must not become live input.
- [ ] Specify accounts/passwords, staff access/recreation, bans/whitelists,
  donations, account banks, rewards, configuration, catalogs, UID allocation,
  audit/erasure evidence, backups and archives. Account-character soft-delete
  includes staff links: prove a staff access path after wipe. Do not infer every
  bank balance or staff character is an approved carryover; list unresolved owner
  policy by affected store. Owner has resolved banks/staff: reset all account-bank
  balances; recreate only exact level-62 Overlords, without old seasonal assets.
- [ ] Cover characters/progression/discoveries; item ownership/equipment;
  inventories, lockers/account lockers/chests/corpses/pets; ships/cargo;
  guilds/alliances/kingdoms/world ownership; auctions/currency; rankings/statistics/
  reports; quests; collectors; Divine Boons and epic-stone claims.
- [x] Remove duplicate schema inventories via the sealed migration manifest;
  lifecycle scanner and runner tests pass. Actual fully migrated DB inventory
  comparison remains in the first W1 item.
- [ ] Seed synthetic old-season data/carryovers, connected/linkdead characters,
  pending saves/outbox records, recovery receipts, Redis and external-client state.
  Reuse `run_copyover_runtime_journey.py`, `test_flatfile_combat_journey.py` and
  `scripts/persistence_restore.py` fixture/private-database patterns.

Exit: every store has a disposition and assertion. Unresolved destructive policy
choices remain explicit readiness blockers, not inferred defaults.

### W2 — Quiesce writers before the irreversible boundary (6–10 hours)

- [ ] Exercise nonstaff/underlevel staff, malformed requests, exact confirmation,
  cancellation/countdown boundaries, repeated requests and issuer disconnect.
  Align help/runbook behavior; ordinary reboot/copyover must never enter reset.
- [ ] Order preparation: validate dependencies/recovery prerequisites, stop new
  seasonal work, settle or safely cancel accepted work, confirm no writer can
  commit, then establish the boundary. Reuse coordinator, outbox, player-save,
  locker, maintenance and Redis controls. Inspect load completions and account/
  donation writers. Preserve accepted benefits while blocking stale character
  writes; pause only writers that can mutate the reset contract.
- [ ] On pre-boundary preflight/quiescence failure, resume service and prove the
  old season remains intact. Do not discard accepted saves and call cancellation
  harmless. Once boundary COMMIT may have succeeded, never resume the old world.
- [ ] Suppress post-reset writebacks, including kingdom flushes and completion
  callbacks. Preserve diagnostics/telemetry according to contract. Prove queued
  shared-writer jobs are covered; coordinator teardown alone is insufficient.
- [ ] Trace retained outbox/journal/checkpoint/authority startup replay. Fence or
  retire old effects at existing consumers when draining cannot prevent replay.
  Add epoch fields only where necessary, with compatibility for historical records;
  do not stamp every table by default.

Exit: hold old saves/operations during preparation, release at former race points,
and prove they cannot recreate reset data. A pre-boundary abort preserves accepted
old-season work and normal saves continue.

### W3 — Durable completion through filesystem cleanup (6–10 hours)

- [x] Extend the singleton only with phase/receipt information needed to distinguish
  incomplete SQL, SQL-ready filesystem cleanup and completed reset. Resume uses
  the same reset identity/epoch. Use additive guarded migrations; do not change
  previously applied immutable migrations.
- [ ] Keep startup fenced until SQL, reward processing, required Redis cleanup,
  filesystem cleanup and all postconditions succeed. Use truthful stage messages;
  final activation must be guarded by expected reset identity.
- [x] Distinguish a fenced failed stop from permission to clean files. Exit 55
  alone cannot authorize deletion after post-boundary SQL failure. The launcher
  must verify durable state or a handoff bound to it, preserving failure status
  through logging/notification commands.
- [x] Preflight artifact, target layout and access before destructive SQL. Revalidate
  canonical targets during cleanup; reject unexpected symlink/path escape, denied
  access and partial deletion. Preserve accounts/config/backups. Repeating cleanup
  for the same unfinished reset must be safe.
- [ ] Make direct launcher and production service honor intentional pwipe stop
  and incomplete-reset fencing, using the existing exit contract with explicit
  non-restart status where needed. Preserve ordinary reboot/crash recovery. Direct
  server starts must also honor the fence.
- [ ] Document/exercise resume at each irreversible stage and restore of a matched
  pre-wipe DB/filesystem/Redis generation. Resume cannot increment epoch again or
  repeat rewards. Never bypass recovery by simply setting state active.

Exit: interruptions after SQL, within file deletion and before final activation
keep startup fenced. Verified completion permits explicit fresh start; duplicate
completion is safe and overall success appears only after all required stages.

### W4 — Reset completeness and exactly-once carryovers (4–8 hours)

- [ ] Reconcile W1 with SQL in child-before-parent order; extend required preflight/
  postflight tables, columns and actions. Test actual values/defaults, not just
  empty counts. Separate active ownership/catalog/baseline state from history.
- [ ] Correct retained active state that crosses seasons, including world ownership
  and snapshots. Preserve history while blocking old payload startup/replay.
  Prove banks, IDs, quests and economic/item baselines match the contract rather
  than blindly following `retain` labels.
- [x] Bind reward-policy application to the resetting epoch and fixed boundary;
  failure prevents SQL-ready publication. The native real-hook matrix proves
  28-day business protection, delayed retries, rollback/lost ACK and unconditional
  old-body summon cleanup. See the reward-retry chunk above.
- [ ] Test permanent, time-expiring, finite-one/finite-many grants, both preserve
  settings, summons, ambiguous commit, immediate/delayed retries, distinct resets
  inside/outside 28 days and failure before activation. Prove new-character claims
  against surviving accounts behave correctly.
- [ ] Reconcile files with actual MariaDB fallback/startup reads. Isolate retained
  recovery evidence instead of loading it as new gameplay. Prevent stale copyover
  files from reattaching old characters/descriptors.

Exit: reset data is absent/inactive with correct defaults; carryover sentinels
survive except documented transitions; retries neither double-consume rewards
nor suppress an independent reset's required cleanup.

### W5 — Website, Redis and telemetry cutover (3–6 hours)

- [ ] Exercise Redis enabled, disabled, unavailable before reset, failing after
  boundary, and re-enabled in the new epoch. Old data/events stay invisible and
  unrelated namespaces survive. Extend `test_redis_maintenance_live.py` and
  season-scope tests rather than building another subsystem. Redis-on/off actual
  journeys and real pre/post-boundary provider failures now pass; re-enable with
  retained old recovery payloads remains open.
- [ ] Exercise website presence, cached lists/leaderboards, account characters,
  websocket/reconnecting clients and queued donations against the disposable
  reset. Verify website writers cannot race it, including stale subscriptions
  during `resetting` and refresh. Link necessary DurisWeb fixes to #264 with their
  revisions/tests; required untested integrations remain open.
- [ ] Specify telemetry season-ID change and sender stop/drain/rebind/start order,
  historical events, identity separation and same-day quota conservation. Reuse
  protected outage-ledger tools and local HTTP receiver. Never delete/reinitialize
  quota evidence or send fixtures to production PostHog.
- [ ] Document remaining manual steps, owner, expected state and verification,
  including backup generation validation and external writer pause/resume. Rehearse
  them; the issue permits documented manual cutover.

Exit: observations belong to the correct season, clients cannot revive old state,
and donations and retained telemetry/quota evidence remain correct.

### W6 — Full journeys and failure/recovery cases (6–10 hours)

- [x] Add `tests/async/run_pwipe_runtime_journey.py`, reusing private DB/world/socket
  fixtures. PR #317 executes the real five-minute command, launcher/wiper, explicit
  new season, recreated Overlord login, fresh mortal gameplay and another boot.
  Qualified scope: MariaDB-primary, Redis off, mini world. Wider cases remain below.
- [ ] Use independent database, Redis process/namespace, ports and runtime tree.
  Never source the checkout's `.env` or read real player/account data. Disable
  production mail/Discord/PostHog in fixtures; artifacts belong under `bin/`.
- [ ] Assert SQL/filesystem/Redis/recovery results, log into an existing account,
  recover staff access by the documented route, create/play a mortal, claim
  benefits, gain progression/items, save/rent, reconnect and reboot again. Prove
  fresh state persists and old characters/items/world ownership never return.
- [ ] Before boundary: unavailable DB/Redis, missing schema, absent/nonexecutable
  wipe artifact, denied file access and quiescence timeout leave the old season
  intact. Invalid/cancelled requests cannot change epoch or invoke cleanup.
- [ ] After boundary: fail SQL, ambiguous COMMIT, Redis invalidation, rewards, file
  cleanup and final activation. Interrupt server and launcher separately at
  SQL/filesystem/completion boundaries. Attempt direct start, repeated launcher
  invocation and service restart against incomplete state.
- [ ] Exercise resume and disposable restore, including interruption after reward
  commit but before completion. Preserve backup/audit sentinels and unrelated
  Redis keys through repeated cleanup attempts.
- [x] Execute production-template sandbox/restart behavior in an isolated real
  system service. The production-profile mini-world journey proves exit 58/55
  stay stopped with zero restarts, then explicit startup/fresh gameplay/reboot.
  The fixture changes identity/path/description and the mini-world launch flag;
  it preserves every sandbox/restart setting. Ordinary exit-52 restart policy
  evidence from the earlier isolated systemd execution remains valid.
- [ ] Fully qualify MariaDB-primary with Redis on/off. Build flat-file mode and
  execute unsupported-pwipe rejection, proving no data loss and normal continuation.
  Flat-file rejection/continuation is now proven by the actual client-free server
  journey. MariaDB Redis-off and Redis-on/systemd core journeys passed (see recorded
  revisions); final optional integration coverage remains open. Record build
  profiles, enabled optional systems and gaps; do not label rejection successful
  flat-file wipe qualification.

Exit: record revisions, sanitized configuration, commands, before/after assertions,
exit statuses, durable phases and recovery outcomes. Fix every blocker and rerun
its failing path, not just the happy path.

### W7 — Review, handoff and readiness (3–6 hours)

- [ ] Reapply ablation: each file has a traced consumer/requirement. Remove
  speculative layers, duplicate state, obsolete paths and task-created scratch;
  preserve unrelated work.
- [ ] Run required formatting/builds, focused checks and final journeys. Update
  runbook, configuration/reward help, regression index and plan to match code.
  Complete applicable reviews; do not wait for CI instead of local qualification.
- [ ] Give findings a disposition: fixed with proof, disproven with proof, explicit
  policy decision, or blocker. Keep #264 and #97's Wipe system item open until
  contract/runbook, gameplay journey, failure/recovery proof and blocking repairs
  are complete. Separate qualification from deployment/production authorization.

## Ablation decisions

- **Keep** launcher/service journeys, durable completion, writer fencing,
  reset-specific carryover accounting and failure tests: omitting these leaves
  demonstrated cross-process/replay risks unproved.
- **Simplify** with the existing singleton, Redis maintenance, worker APIs,
  migration runner, manifest and fixtures. No new coordinator service, generic
  wipe framework or parallel manifest is needed.
- **Drop** blanket ledger deletion/epoch columns, new flat-file reset support,
  repository-wide burn-in and unrelated cleanup. Add isolation/tests for actual
  consumers; do not trade away acceptance requirements.
- **Keep** the confirmed owner policy: every account-bank balance resets; only
  exact level-62 Overlords are recreated. **Investigate** protected recovery
  consumers and prove approved reward carryovers; retained stores remain in
  completion criteria.

## Validation recorded during planning

These commands passed on the baseline in an isolated source worktree without
executing a wipe or contacting production:

```text
python3 tests/async/test_pwipe_quiescence.py
python3 tests/async/test_sql_pwipe_completion.py
python3 tests/async/test_cycle_pwipe_status.py
python3 tests/async/test_redis_pwipe_invalidation.py
python3 tests/async/test_season_reset_fence.py
python3 tests/async/test_season_reset_manifest.py
python3 tests/async/test_redis_season_scope.py
python3 scripts/validate_data_lifecycle.py
bash -n scripts/cycle_mud.sh Players/wipers/wipe_it_all
```

`python3 tests/async/test_data_lifecycle_manifest.py` ran 12 tests with five
failures. Its overridden schema list omits `0048_divine_boon_state.sql`; validation
reports unknown `divine_boon_state`, masking four expected-error assertions. The
standalone validator includes it and passes (199 tables, 24 stores, 42 Redis
surfaces). W1 repairs the divergence; neither result proves live-schema coverage.
The seven passing pwipe/season tests are source contracts, not runtime wipe,
race, filesystem, systemd or gameplay qualification.

Implementation completion must include, as applicable:

```text
./scripts/format.sh --check
make -C src PERSISTENCE_BACKEND=mariadb
make -C src PERSISTENCE_BACKEND=flatfile BIN_ROOT=<absolute-path-under-bin>
python3 tests/async/test_data_lifecycle_manifest.py
python3 tests/async/test_redis_maintenance_live.py
```

Also rerun the seven source contracts, affected subsystem executable tests,
existing account reward schema tests, and the planned journey/failure cases.
Choose the new runner's interface during W6; never record future commands as
executed. Use separate backend output directories to avoid stale builds.

## Estimate and uncertainty

**32–56 active engineering hours (about 4–7 eight-hour working days)** for one
implementer, including W1–W7, tests, builds, review fixes and evidence. Work-item
ranges sum to this total; they are not parallel-agent estimates. Planning and
publication in this change are separate from implementation. This is a forecast,
not a fixed budget or promised date, and does not establish October 28 readiness.

Largest uncertainties: retained authority/recovery replay, cross-process recovery
changes, and companion website/quota cutover. Disposable systemd/DB/Redis access
and owner policy decisions can add calendar delay. Re-estimate after W1 and the
first real reset journey, and immediately when findings invalidate the range.
Do not silently drop acceptance items to preserve the estimate.
