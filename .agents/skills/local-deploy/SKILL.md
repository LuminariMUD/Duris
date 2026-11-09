---
name: local-deploy
description: >-
  Deploy the local Duris MUD from current master: pull, migrate, fully clean-build,
  install, and restart immediately through cycle_mud.sh with fresh .env settings.
  Use for local/dev deployment, without systemd or player-content preparation.
---

# Local Deploy

An invocation authorizes this local deployment through verification. Creating or
editing the skill does not deploy. Require `ENVIRONMENT=local`; use
[$deploy-production](../deploy-production/SKILL.md) for production instead.
Skip news, help, bug triage, countdowns, broad regression suites, and commit/push.
Use the existing checkout and scripts. Local downtime during migration/build is
acceptable; keep the database and Redis running.

## 1. Pull current master

Read `.env` without displaying credentials and confirm the environment. Resolve
the Git root, inspect branch/status, and preserve unrelated edits. Switch to
`master` if necessary, then run:

```bash
git pull --ff-only origin master
git fetch origin master
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/master)"
```

Require the branch to be `master`, and record its SHA. If master belongs to
another worktree, the pull fails, or local commits/edits prevent a safe update,
resolve that specific condition without discarding work or forcing Git operations.
Do not proceed detached or deploy a different branch.

## 2. Stop the local launcher and apply migrations

Identify this checkout's game PID, launcher PID, executable hash, listener ports,
and launch flags from live processes. Preserve those flags, including an existing
no-argument launch; use `--dev` for a new local instance. Never stop a sibling
checkout by matching only a name or port. If the game is running, preserve its
executable bytes (`cp -L /proc/<game-pid>/exe ...`) and backend stamp outside
`bin/`, which `clean-all` removes. Keep a regular executable file, not a proc symlink.

For a legacy `duris-mud.service` that owns this checkout, stop and disable it,
remove its local unit file, and reload the user daemon. Otherwise send SIGTERM
to the verified **launcher** PID: it forwards the signal, drains the game, and
ends its restart loop. Wait for both processes and their listeners to exit.
Stopping only the child lets the old launcher restart it with stale settings.
Do not create or enable a local systemd unit.

Export the current configuration without shell tracing:

```bash
set -a
source .env
set +a
```

Run these in order:

```bash
python3 scripts/migration_runner.py run
./migrations/verify_runtime_compatibility.sh
```

Refuse any `PERSISTENCE_MODE` other than `mariadb-primary`. Complete
configuration/dependency setup required by the pulled release, preserving intentional
local settings. Do not replay historical import, repair, or wipe scripts. A failed
migration must be resolved before starting a writer; never bypass the runner's checks.

## 3. Rebuild everything from clean sources

Run each command only after the previous succeeds:

```bash
make clean-all
make -j4 BUILD_PROFILE=development
make -C src -j4 pfile telemetry-state BUILD_PROFILE=development
make -C migrations/tools -j4 all affects pfile_converter
make world
./scripts/cycle_mud.sh --check-config
```

This covers the server, editor, area generators, pfile and telemetry tools,
migration utilities, and freshly generated world/lookups. Require an executable
`bin/server/dms_new`, its `.dms_new-backend` stamp equal to
`mariadb/development`, complete nonempty generated outputs listed in the
root Makefile, and no missing shared libraries. Fix build failures before
installing or starting anything; do not substitute an old binary for the build.

## 4. Install and restart immediately

Record the new binary's SHA-256, then install by same-filesystem rename:

```bash
mv bin/server/dms_new bin/server/dms
mv bin/server/.dms_new-backend bin/server/.dms-backend
./scripts/start_mud.sh # append the launch flags recorded in step 2
```

Start as soon as installation succeeds, with no player countdown. A **fresh
`cycle_mud.sh` process is required on every deployment**: it sources the current
`.env`. An in-game reboot or copyover retains the old launcher's exported values;
the game's `.env` loader deliberately does not overwrite inherited variables.
Never copy over a running executable inode or launch a second supervisor.
`start_mud.sh` uses `nohup setsid` so the launcher survives the calling shell.
The launcher regenerates `lib/misc/event_names` from the installed binary.

## 5. Verify the actual running game

Follow `logs/duris-console.log` and the new `logs/log/` output through startup.
Require `Entering game loop.`, the intended listeners owned by the new game PID,
and `/proc/<pid>/exe` matching the installed SHA-256 and backend stamp.
Startup item-ownership checks can take several minutes; continue observing a
live process rather than rebooting it because a short observation timed out.

Compare the running process's environment with the shell-sourced `.env` values
for every configured variable, without printing secrets. In particular verify
`CHAOS_MUD`, `CREATION_ALL_RACES`, and `CREATION_ALL_CLASSES`, and check that a
fresh login banner advertises only enabled modes. Follow the
[authenticated smoke procedure](../../../docs/operations/RUNBOOK.md#authenticated-post-deployment-smoke)
using the configured test account, then log out cleanly. Use HTTP health only
when its listener is enabled. Check for new crashes, restart loops, or persistence
errors. Require no active/enabled `duris-mud.service` for this checkout.

Report the master SHA, migration result, clean build, installed/running binary
identity, launcher/port, and configuration/login verification. Leave any real
failure explicit; never call a merely listening or still-booting game deployed.
