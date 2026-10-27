---
name: deploy-production
description: >-
  Deploy native Duris production from master while keeping players online during
  preparation and the full clean build. Apply migrations online whenever safe;
  stop writers only when live evidence proves it is absolutely necessary. Reboot
  as Veridian after a 180-second warning and verify the running game.
---

# Deploy Production

Execute the six steps below in the existing production checkout. An explicit
request to deploy authorizes the production migrations, missing-help authoring
and publication, bug-report investigation and necessary GitHub issue creation,
clearing fully processed feedback, build, scheduled in-game reboot, and final
commit/push of the verified news file directly to `master` described here. Do not
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
- Before preparing news, follow
  [player feedback](references/player-feedback.md) to snapshot `lib/etc/help`
  and `lib/reports/bugs`, investigate missing-help requests, and author and
  publish useful missing topics or aliases end to end. Also update help affected
  by the release. Finish help publication and player-visible lookup verification
  before writing its news coverage; retain unsuccessful requests for retry.
- Follow [news-update](../news-update/SKILL.md) to prepare
  `lib/information/news` for missing player-facing changes in the release.
  Record its existing staged and unstaged changes before editing so the final
  news commit can distinguish this deployment's work from unrelated edits.
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
- Process bug reports using [player feedback](references/player-feedback.md)
  at any point after the pull, independently of help/news. Prefer online
  preparation so completed entries are ready for cleanup at the scheduled
  restart. Check existing issues and PRs and create verified issues for real
  untracked bugs. Triage itself is not player news and does not authorize
  implementing unrelated bug fixes during deployment. Unclear reports or GitHub
  failures remain pending; they do not by themselves block an otherwise qualified
  deployment. Report unfinished feedback work separately.
- Complete other setup required by the pulled release before the build. An
  in-game reboot does not replace the existing launcher or systemd environment;
  account for an actual change to either, rather than assuming it takes effect.

A preparation failure leaves the current game running. Resolve or report the
concrete error; do not stop services to work around it or reboot an incompatible release.

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

### Offline migration only when proven unavoidable

Before announcing any outage, require the completed build, generated world, checked
configuration, recovery executable/stamp, and prepared content. No compilation,
world generation, release research, or unrelated setup belongs inside the outage.
Identify the game child, launcher, website workers and scheduled jobs using this
database, and record their service states. Confirm the user-scope MUD service sends
SIGTERM to the launcher (`KillMode=mixed`) and allows the child enough time to drain.

Log in as Veridian using the account/menu guidance below and check `time` for
another operator's schedule. Broadcast exactly:

```text
echoa Maintenance begins in 180 seconds: Zusuk has new code incoming, brace for impact!
```

Keep Veridian connected for the full warning. Then stop the configured user-scope
MUD service, targeting the launcher while its child is running. The launcher forwards
SIGTERM, waits for graceful exit, and leaves its restart loop. Do not use child-only
`shutdown ok`, which lets the launcher restart after ten seconds. Stop only the other
writers the migration actually requires, prevent their automatic restart, and verify
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

Prepare the [feedback cleanup](references/player-feedback.md#clear-processed-feedback)
before announcing the reboot. Serialize it with the launcher so it runs only
after the old child and its log writer have exited and before a new child can
write reports. Use the already-required restart or proven offline-migration
window; do not add a shutdown for housekeeping. Re-read the files, remove only
successfully processed snapshot entries, and preserve later arrivals and pending
work. Keep this operation short; research, issue creation, and help publication
belong in step 2. Restore the launcher's normal operation promptly even if cleanup
fails. If a safe handoff cannot be established, retain the files and report cleanup
as pending instead of racing the running writers.

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
Confirm the game's countdown/message. Keep Veridian connected and observe the
countdown until the server disconnects for reboot. Do not resend `shutdown` to
check progress; it can cancel or replace a pending shutdown. Use `time` instead.

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
schema. Report unresolved failures with the actual service state. Completion
means the rebuilt game is running and healthy, not merely that reboot was
scheduled. Report the revision, migrations/content changed, build result, and
restart/log/health result concisely. Include help topics added, bug dispositions
and created/existing issue or PR links, and whether each feedback file was cleared
or retains new/unresolved entries. Do not call feedback processing complete when
publication, issue creation, or cleanup remains pending.

In case of disaster, use the preserved executable and stamp only when the current
database passes that binary's matching runtime contract. After a migration advances
the required head, keep the game stopped until a compatible binary is available or
an authorized recovery restores the matching database backup. Do not blindly pair
the old binary with the new migration history.

## 6. Commit and push the verified news directly to master

After the game is healthy and the changed news has passed database equality and
in-game readback, commit `lib/information/news` and push it directly to `origin/master`.
This is part of deployment completion, under the authorization above. Keep the
deployed code revision/hash separate from this later news-only commit in the report.

Confirm this checkout is still on `master`, inspect the full news diff against
the recorded starting state, and run `git diff --check -- lib/information/news`.
Commit only news that was included in the verified publication/readback. Preserve
unrelated staged and unstaged work, including help sources, feedback, and generated
files; do not use `git add -A` or an unrestricted commit. If unrelated edits share
the news file, isolate the deployment's changes before committing; report the
specific conflict if they cannot be separated safely.

Fetch `origin master` and inspect the outgoing commit range before pushing. It
must contain only the intended news update, not unrelated unpublished commits.
For an isolated news-file diff, use:

```bash
git commit --only -m "docs: update player news after deployment" -- lib/information/news
git push origin HEAD:master
```

Inspect the resulting commit before executing the push. Do not create an empty
commit when news is unchanged. On a resumed run, reuse an existing verified news
commit and finish its push rather than creating a duplicate.

Never force-push or bypass branch protection. On a non-fast-forward rejection,
fetch and inspect the new remote state; do not blindly pull unbuilt code into the
verified production checkout or overwrite another news update. If safe reconciliation
is not possible within this deployment, preserve the local commit and report the
push as pending. Authentication or branch-policy failures likewise leave the healthy
game running and the commit available for retry; do not claim a successful push.

After pushing, refresh the remote ref and verify that `origin/master` contains the
news commit and that its news file matches the verified published content. Report
the commit SHA and push result. The news handoff is complete only when that remote
verification succeeds, or when there was no news change or outstanding news commit.
