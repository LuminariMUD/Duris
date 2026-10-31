---
name: deploy-production
description: >-
  Deploy native Duris production from master while keeping players online during
  preparation and the full clean build. Apply migrations online whenever safe;
  stop writers only when live evidence proves it is absolutely necessary. Reboot
  as Veridian with a full 180-second countdown, finish player feedback, verify
  the running game, and commit/push the deployment's content and feedback changes.
---

# Deploy Production

Execute the six steps below in the existing production checkout. An explicit
request to deploy authorizes the production migrations, missing-help authoring
and publication, website help-submission reviews and their normal notifications,
bug-report investigation and necessary GitHub issue creation,
clearing processed feedback (including unclear requests rejected after investigation),
build, scheduled in-game reboot, and final commit/push of verified news, help sources,
and feedback cleanup directly to `master` described here. Do not
stop at a handoff or ask again for those actions. Editing this skill does not
execute a deployment, process live feedback, or commit/push repository changes.
Keep the game and website running during preparation, compilation, world generation,
content publication, and migrations that can safely run online. **An offline migration
is a last resort, allowed only when evidence from the actual pending operation and
live database proves that stopped writers are absolutely necessary.** Finish the
entire build and all independent preparation before any migration outage. The normal
announced reboot remains the final cutover; do not turn it into a build outage.

A pending migration, migration number (including 0041), newer runtime contract,
missing online flag, or runner quiescence refusal is **not** proof that downtime is
necessary. Never automatically fall back to stopping services. If tooling lacks a
safe online path, resolve that limitation while the game stays up, or report it and
leave the game running. Do not bypass safeguards or claim an unproven outage is required.

Treat merged master as qualified. Do not create worktrees, temporary deployment
environments, cloned databases, or containers. Do not run burn-in, regression
suites, restore drills, broad audits, or CI gates. Validate the build and the
actual restarted game. Newly authored help still needs source, format, import,
and in-game verification as described below. Preserve unrelated edits, secrets,
and player data.

## 1. Pull immediately

After a quick branch/status check and recording the pre-pull HEAD, run this in
the production checkout on master as the first substantive operation:

```bash
git pull --no-rebase origin master
```

Resolve conflicts in this checkout, preserving local work and production
settings. Do not reset, clean, or discard changes to force the pull through.
Record the resulting revision; do not delay the pull for release inventories,
backups, builds, or a separate integration workspace.

## 2. Prepare migrations, content, and setup while the game stays online

Read the required `.env` settings without displaying credentials. Confirm
`ENVIRONMENT=production` and the configured database target. This host uses
user-scope systemd; its `staging` account name does not mean a staging environment.
Use the pulled changes to determine necessary configuration, dependency, seed,
help, news, and installed-job updates. Preserve intentional production overrides.
Consult subsystem documentation only for the operations that actually apply.

- Before database/content changes, take a backup with `scripts/backup_pfiles.sh`.
  If the pulled schema contract is newer than the live database, select the old
  matching manifest through `RUNTIME_COMPATIBILITY_MANIFEST`; retrieve it from
  pre-pull Git history or an existing backup. Keep recovery files outside `bin/`.
- Determine pending migrations from the manifest and **live history**; `inspect`
  alone does not query production. Read each pending apply file and verifier,
  inspect the affected live schema/data and database engine, and check compatibility
  with running writers. Distinguish work already satisfied by the live schema,
  safe online changes, and operations that genuinely require stopped writers.
  For 0041, inspect `pkill_info.log`: an already-canonical MEDIUMTEXT column makes
  the guarded ALTER a no-op. Its migration ID alone never justifies an outage.
- Prefer the exact migration's reviewed online runner path, retaining target,
  backup, checksum, history, verification and bounded-lock safeguards. A no-op SQL
  body still needs safe ledger completion through supported tooling; do not insert
  history manually. A lock timeout is a failed attempt, not permission to shut down.
- Before considering an offline path, identify the specific unavoidable blocking
  operation or incompatible writer and explain why a safe online path cannot serve
  it. Missing tooling or uncertainty is not that evidence. Keep services running
  while resolving either. State the concrete reason and expected outage work to
  the user before issuing a maintenance warning.
- Prepare migration execution now; apply it after the successful build in step 4.
  Use [the migration guide](../../../docs/persistence/IMMUTABLE_MIGRATIONS.md) for
  mechanics, not as a requirement to create a test environment. Do not replay
  historical repair/wipe scripts as though they were pending migrations.
- Record existing staged and unstaged changes in news, help sources (including
  `lib/information/help_index`), and feedback paths before editing. Step 6 commits
  this deployment's verified changes to all of them, preserving unrelated work.
- Invoke [$help-update](../help-update/SKILL.md) before preparing news to
  process `lib/etc/help`, review website Help Suggestions, and update help affected
  by the release. Pass the confirmed production target, pulled revision, backup,
  and recovery directory.
  Require recorded review decisions and verified publication/lookups for accepted
  content from both sources; retain website review history, the log cleanup record
  for step 4, and maintained source changes for step 6. A verified request for
  revisions completes that submission's review while awaiting its author.
- Invoke [$news-update](../news-update/SKILL.md) to prepare
  `lib/information/news` for missing player-facing changes in the release.
  Supply the verified help additions from this deployment as an explicit extra
  content source alongside the GitHub history inventory; they may be local source
  edits, so do not describe them as merged commits. Include useful topics and
  lookup commands, not feedback processing or issue-triage bookkeeping.
  Put the new release headline and main addition before the previous newest
  section, including for another release on the same day. Keep temporary
  deployment notices out of player news.
- With help already published and verified, preview and publish news using
  `scripts/import_help_to_prod.sh --local --news-only --dry-run`, then
  `--local --news-only`. Answer its normal confirmation under the deployment
  authorization. Do not use `--clean` or repeat a bulk help import to publish
  news. Verify stored news bytes; boot will refresh its cache.
- Invoke [$bug-triage](../bug-triage/SKILL.md) after the pull, independently
  of help/news, with the runtime target, pulled revision, and recovery directory.
  Require completed dispositions and verified issue filing before announcing
  the restart. It checks current master, existing issues, and open PRs; retain
  its cleanup record for step 4. Triage is a required deliverable.
- Complete other setup required by the pulled release before the build. An
  in-game reboot does not replace the existing launcher or systemd environment;
  account for an actual change to either, rather than assuming it takes effect.

A preparation failure leaves the current game running. Resolve concrete import,
lookup, or GitHub failures before the routine cutover; if an external failure cannot
be resolved, report the exact blocked action and leave the deployment incomplete.
Do not substitute an issue draft for a verified issue or call unfinished investigation
"unclear" to skip it. Do not stop services to work around a preparation failure or
reboot an incompatible release.

## 3. Complete the full clean rebuild while the game stays online

Identify the running game child, launcher, and executable hash.
Preserve the executable bytes (`cp -L /proc/<server-pid>/exe ...`) and production
stamp in a private recovery directory outside `bin/`: `clean-all` removes that
entire build tree. Keep the game and website running for every build stage,
even when an offline migration has been proven necessary. Do not announce or begin
that outage until the complete build and world generation have passed.

Run each command only after the previous command succeeds:

```bash
make clean-all
```

Immediately restore the preserved current `dms` and `.dms-backend` into `bin/server/`
using temporary files and atomic renames, so the launcher retains a usable current
binary during compilation. Never write over a running executable inode. Then run:

```bash
make -j4 PERSISTENCE_BACKEND=mariadb BUILD_PROFILE=production
make -C src pfile PERSISTENCE_BACKEND=mariadb BUILD_PROFILE=production
make -C migrations/tools all affects pfile_converter
(cd areas && ./m_slow)
```

This rebuilds the server, editor, area generators, and maintenance tools from
scratch, then regenerates the world and lookups. Do not reuse a previous build.
Check build errors, missing dynamic libraries, the seven `areas/world.*` and
five lookup outputs listed in the root Makefile, and an executable
`bin/server/dms_new` with `.dms_new-backend` equal to `mariadb/production`.
Run `scripts/cycle_mud.sh --production --check-config`.

A failed build leaves the current game running. Fix the build before any cutover.
Keep the successful `dms_new` staged until step 4; the old binary must remain the
launcher's target until required migrations have passed.

## 4. Apply migrations, install, and restart with the shortest necessary interruption

With the full build ready, apply **every pending migration**, in manifest order,
using `python3 scripts/migration_runner.py run`. Export `.env`
(`set -a; source .env; set +a`) and supply
`--confirm-production-target "$DB_HOST/$DB_NAME"` and
`--production-backup /absolute/path/to/database.sql.gz`. Refresh an expired backup
while services remain online. Use only the exact manifest's reviewed online option;
never invent an exception or bypass the runner's quiescence guard. Finish with
`migrations/verify_runtime_compatibility.sh`. If the online path fails, keep the game
running and resolve the failure; the evidence requirement in step 2 still applies.

Use the offline procedure below only after satisfying that requirement. Otherwise,
keep services running through migration and installation, then use the normal
scheduled reboot below.

### Player countdown for every cutover

Always use the game's timed reboot/shutdown when it can safely perform the required
cutover. The offline path must meet the same three-minute player warning requirement.
Check `time` before scheduling and do not replace another operator's countdown.
Keep Veridian in play and connected: manual timers cancel if their issuer leaves
play, disconnects, or loses permission. Observe the warnings, using `time` for
status rather than resending `shutdown`.

If the native timer cannot safely perform this cutover, explain the concrete reason
and use repeated `echoa` broadcasts. Announce 180 seconds, then the actual remaining
time at 120, 60, 45, 30, 15, 10, and 5 seconds, followed by a maintenance-begins-now
message before stopping. Use one recorded deadline; wait the full 180 seconds and
do not send stale countdown values after a delay. Keep the session responsive and
capture the returned broadcasts. One announcement followed by a silent wait is
never sufficient. If a native timer's warning updates fail, supply these broadcasts
for the remaining interval after checking its deadline. If the schedule is cancelled
or delayed, tell players and establish a new announced deadline before stopping.

### Offline migration only when proven unavoidable

Before announcing any outage, require the completed build, generated world, checked
configuration, recovery executable/stamp, and prepared content. No compilation,
world generation, release research, or unrelated setup belongs inside the outage.
Identify the game child, launcher, website workers and scheduled jobs using this
database, and record their service states. Confirm the user-scope MUD service sends
SIGTERM to the launcher (`KillMode=mixed`) and allows the child enough time to drain.

Log in as Veridian using the account/menu guidance below and follow
[the countdown requirement](#player-countdown-for-every-cutover). Prefer a timed
`shutdown ok 3 Zusuk has new code incoming, brace for impact!` only when an established
launcher/service handoff prevents automatic restart until migration and installation
finish. Inspect the actual launcher: the current `cycle_mud.sh` restarts even after
child exit 0, so `shutdown ok` alone does not hold writers down. Its ten-second sleep
is not a safe maintenance window. Do not arm a timer that can restart incompatible
writers or improvise a race against their exit.

When that safe timed handoff is unavailable, explain this limitation and use the
repeated-broadcast fallback, starting with:

```text
echoa Maintenance begins in 180 seconds: Zusuk has new code incoming, brace for impact!
```

Keep Veridian connected through all countdown updates. At the announced deadline,
stop the configured user-scope MUD service, targeting the launcher while its child
is running. The launcher forwards SIGTERM, waits for graceful exit, and leaves its
restart loop. With a verified timed handoff, let the timer complete and keep the
launcher stopped instead. Stop only the other writers the migration actually
requires, prevent their automatic restart, and verify
their processes and database sessions have ended. Keep the database and Redis up.
The runner's quiescence check must pass; do not kill unknown sessions or weaken it.

Refresh the backup with writers stopped and the pre-migration runtime manifest.
Apply the prepared migration with the production target/backup arguments and no
online option, verify compatibility, and immediately install the already-built server
as described below. Start the log observation in step 5, perform the prepared
feedback cleanup while writers remain stopped, then restore recorded service
states promptly. Skip failed cleanup rather than delaying restoration. Do not
schedule a second shutdown. If migration or compatibility
verification fails, keep incompatible writers stopped and report the actual state;
never restart an incompatible old binary.

### Atomic installation

Ordinary reboot exits with 52 and executes `bin/server/dms`; the launcher only
promotes `dms_new` for 53/57. After required migrations pass, install the successful
build by same-filesystem atomic rename from `dms_new` to `dms`, move its stamp
to `.dms-backend`, and generate `lib/misc/event_names` with
`scripts/event_names.sh bin/server/dms`. Never truncate or copy over a running
executable inode. Record the new hash and confirm the current process still
uses its original executable when it is still running. For an offline migration,
perform the prepared feedback cleanup before promptly restoring the recorded
services; otherwise schedule the normal reboot below with cleanup coordinated at
its restart boundary. Do not restart after a failed build.

### Retire processed feedback at the existing restart boundary

Use the cleanup records returned by `$help-update` and `$bug-triage` and the shared
[feedback cleanup procedure](../references/player-feedback.md#clear-processed-feedback).
Prepare it before announcing the reboot and execute it at the already-required
restart or proven offline-migration boundary. Restore normal launching promptly
even if cleanup fails; report each file's verified result for steps 5 and 6.

### Normal reboot as Veridian (no offline migration)

Use the account credentials in `.env` to log in over the configured game
connection and select the Overlord character **Veridian**. Handle the account
menu, reconnect, and pager prompts. Check `time` for an existing staff shutdown;
do not silently replace another operator's schedule.

Issue exactly:

```text
shutdown reboot 3 Zusuk has new code incoming, brace for impact!
```

The numeric argument is **minutes**: `3` means the requested **180 seconds**.
Confirm the game's countdown/message and follow
[the countdown requirement](#player-countdown-for-every-cutover) until disconnect.

Keep Veridian logged in through the reboot. Answer any questions asked to you
on any of the channels to the best of your ability, but add a little note
that you are an AI Agent.

## 5. Watch the logs and verify the game returns

Start observing before the reboot and continue through startup. Follow the
user-unit journals for the MUD, database, Redis, and website, the console log,
and all new output in `logs/log/` and `logs/player-log/`. Follow files created or
rotated during reboot too. Review the output, not just matching error words.

Require the new server child's `/proc/<pid>/exe` hash to match the rebuilt
binary, the production stamp to match, and startup/world/persistence loading to
complete without unresolved errors. Check `scripts/healthcheck.sh`, public MUD
health at `https://ws.duris.sbs/health`, and website health at
`https://duris.sbs/health`. Reconnect to confirm the game accepts logins.
When news changed, run `news` and complete the player-visible readback in
[news-update](../news-update/SKILL.md): verify the newest headline and main
addition on the first page and read through the new section. Database equality
or a successful help lookup does not replace this check. Report any incomplete
readback. Then quit the deployment character and close your session. Observe
another minute of normal operation for crashes, restart loops, or recurring errors.

Diagnose any failure from the logs and fix direct deployment mistakes where
possible; do not blindly repeat reboots or roll old code onto an incompatible
schema. Report unresolved failures with the actual service state. Deployment
completion requires a healthy rebuilt game, finished feedback dispositions and
cleanup, verified content, and the commit/push in step 6. Report the revision,
migrations/content changed, build result, and restart/log/health result concisely.
Include help topics added, website suggestion IDs and review outcomes, bug dispositions
and created/existing issue or PR links, and whether each feedback file was cleared
or retains new arrivals or entries blocked by a concrete failed operation. Count
rejected unclear entries as processed, not pending. Do not call the deployment
complete when publication, issue creation, cleanup, or required push remains pending.

In case of disaster, use the preserved executable and stamp only when the current
database passes that binary's matching runtime contract. After a migration advances
the required head, keep the game stopped until a compatible binary is available or
an authorized recovery restores the matching database backup. Do not blindly pair
the old binary with the new migration history.

## 6. Commit and push verified content and feedback directly to master

After the game is healthy, commit and push all of this deployment's verified
changes directly to `origin/master`: `lib/information/news`,
`lib/information/help_index`, any other maintained help source actually changed,
and the processed cleanup of `lib/etc/help` and `lib/reports/bugs`. News requires
database equality and in-game readback; help requires the publication/lookup
checks in step 2; feedback requires verified cleanup at the restart boundary.
Do not leave help or report changes for a separate handoff. This step still applies
when news is unchanged. Keep the deployed code revision/hash separate from these
later content/cleanup commits in the report.

Confirm the checkout is still on `master`. Review each diff against its recorded
starting state and run `git diff --check` and `git diff --cached --check` on the
exact intended paths. Isolate only the verified deployment changes, preserving
unrelated staged and unstaged work.
Use an isolated Git index when needed; do not use `git add -A` or an unrestricted
commit. If shared-file changes cannot be separated safely, report the specific
conflict rather than including unrelated work.

The two runtime feedback files are currently ignored. Do not silently omit their
cleanup or broadly unignore runtime directories. For each feedback file whose
captured batch was fully retired and cleanup verified, record an empty baseline
using an explicit path-scoped index entry even if the path was ignored/untracked.
New arrivals stay byte-for-byte in the live files and out of
the commit; stage the verified cleared baseline without overwriting the live file.
Do not use `git commit --only` on those paths, since it rereads the live contents.
Keep raw reports, identities, and recovery snapshots private. If HEAD already has
the same empty baseline, no new feedback-file diff is needed; explain any remaining
worktree differences as new arrivals. Never record a cleared baseline for failed
cleanup or a batch with unfinished dispositions.

Fetch `origin master` and inspect the outgoing commit range. It must contain only
the intended content/cleanup updates, not unrelated unpublished commits. Commit
the reviewed index with an appropriate message, inspect the resulting commit(s),
then run `git push origin HEAD:master`. Do not create an empty commit. On a resumed
run, reuse verified unpublished commits and finish their push; include any remaining
verified help/cleanup changes without duplicating earlier content.

After committing with an isolated index, reconcile only the committed changes in
the regular index while preserving unrelated staged hunks and all live file bytes;
do not leave the old index staging reversals of the new commit.

Never force-push or bypass branch protection. On a non-fast-forward rejection,
fetch and inspect the new remote state; do not blindly pull unbuilt code into the
verified production checkout or overwrite another content update. If safe reconciliation
is not possible within this deployment, preserve the local commit and report the
push as pending. Authentication or branch-policy failures likewise leave the healthy
game running and the commit available for retry; do not claim a successful push.

After pushing, refresh the remote ref and verify that `origin/master` contains every
intended commit, its news/help bytes match the verified publication, and its feedback
baselines match the verified cleanup. Report commit SHAs and push results. The handoff
is complete only after this verification, or when there are no deployment changes
or outstanding deployment commits.
