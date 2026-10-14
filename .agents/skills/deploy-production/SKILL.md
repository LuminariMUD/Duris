---
name: deploy-production
description: >-
  Deploy native Duris production from master: pull immediately, apply pending
  migrations and content updates, do a full clean rebuild, reboot as Veridian
  after a 180-second warning, and watch the logs until the new game is healthy.
---

# Deploy Production

Execute the five steps below in the existing production checkout. An explicit
request to deploy authorizes the production migrations, content publication,
build, and scheduled in-game reboot described here. Do not stop at a handoff or
ask again for those actions. Editing this skill does not execute a deployment.
When a pending migration requires stopped writers, the deployment includes the
announced maintenance outage described below.

Treat merged master as qualified. Do not create worktrees, temporary deployment
environments, cloned databases, or containers. Do not run burn-in, regression
suites, restore drills, broad audits, or CI gates. Validate the build and the
actual restarted game. Preserve unrelated edits, secrets, and player data.

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

## 2. Finish migrations, content, and related setup before building

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
- Apply **every pending migration**, in manifest order, with
  `python3 scripts/migration_runner.py run`. Compare against live history; `inspect` alone
  does not query production. Export `.env` (`set -a; source .env; set +a`) and
  supply `--confirm-production-target "$DB_HOST/$DB_NAME"` and
  `--production-backup /absolute/path/to/database.sql.gz`, plus the supported
  online option only when the exact pending manifest has already-reviewed online
  support. Otherwise use the offline procedure below; never invent an online
  exception or bypass the runner's quiescence guard. Use
  [the migration guide](../../../docs/persistence/IMMUTABLE_MIGRATIONS.md) for
  those mechanics, not as a requirement to create a test environment. Do not
  replay historical repair/wipe scripts as though they were pending migrations.
  Finish with `migrations/verify_runtime_compatibility.sh`.
- Update help when the release changes it.
  The importer gives `help/duris_help_parsed.hlp` precedence over
  `lib/information/help_index`; correct colliding stale entries. Run the innate
  help generator only when relevant.
- Follow [news-update](../news-update/SKILL.md) to prepare
  `lib/information/news` for missing player-facing changes in the release.
  Put the new release headline and main addition before the previous newest
  section, including for another release on the same day. Keep temporary
  deployment notices out of player news.
- Preview and publish changed content using
  `scripts/import_help_to_prod.sh --local --dry-run`, then `--local`.
  Use `--news-only` for both commands when only news changed. Answer its normal
  confirmation under the deployment authorization. Do not use `--clean`.
  Verify the changed stored entries and news bytes; boot will refresh caches.
- Complete other setup required by the pulled release before the build. An
  in-game reboot does not replace the existing launcher or systemd environment;
  account for an actual change to either, rather than assuming it takes effect.

A migration or required setup failure is a real blocker: resolve it or report
its concrete error. Do not skip it and reboot an incompatible release.

### Offline migrations, including 0041

Before invoking the runner for an offline step, identify the game child, launcher,
website workers and scheduled jobs that use this database, and record their service
states. Preserve the running executable and stamp in the private recovery directory
described in step 3 before stopping the game.

Log in as Veridian using step 4's account/menu guidance, check `time` for another
operator's schedule, and issue `shutdown ok 3 Zusuk has new code incoming, brace for impact!`.
Confirm the 180-second countdown and stay connected until the graceful shutdown
completes. Stop the configured user-scope launcher, website workers and database jobs;
prevent their automatic restarts for the outage and verify their processes and
database sessions have ended. Keep the database and Redis available. The runner's
own quiescence check must pass; do not kill unknown connections or weaken the check.

Refresh the backup after writers stop, using the pre-migration runtime manifest.
Apply pending migrations with the normal production target/backup arguments and no
online option, then verify runtime compatibility. Keep these writers stopped through
content updates, the clean build and atomic binary installation. If any step fails,
keep the incompatible game stopped and report the actual service state.

## 3. Do a full clean rebuild

If the game is still running, identify its child, launcher, and executable hash.
Preserve the executable bytes (`cp -L /proc/<server-pid>/exe ...`) and production
stamp in a private recovery directory outside `bin/`: `clean-all` removes that
entire build tree. For an offline migration, use the executable already preserved
before shutdown and keep writers stopped. Otherwise keep the game alive during the build.

Run each command only after the previous command succeeds:

```bash
make clean-all
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

Ordinary reboot exits with 52 and executes `bin/server/dms`; the launcher only
promotes `dms_new` for 53/57. Before scheduling the reboot, install the successful
build by same-filesystem atomic rename from `dms_new` to `dms`, move its stamp
to `.dms-backend`, and generate `lib/misc/event_names` with
`scripts/event_names.sh bin/server/dms`. Never truncate or copy over a running
executable inode. Record the new hash and confirm the current process still
uses its original executable when it is still running. Do not restart after a failed build.

## 4. Schedule the reboot as Veridian

For the offline path, the warning and shutdown already occurred in step 2. Restore
the recorded service states with the newly installed server and continue directly
to step 5; do not schedule a second shutdown. Observe logs before starting services.

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
restart/log/health result concisely.

In case of disaster, use the preserved executable and stamp only when the current
database passes that binary's matching runtime contract. After a migration advances
the required head, keep the game stopped until a compatible binary is available or
an authorized recovery restores the matching database backup. Do not blindly pair
the old binary with the new migration history.
