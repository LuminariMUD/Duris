# Issue #417: local pwipe qualification workspace

## Retirement, 2026-10-28

The owner retired this completed local test environment. The
`duris-issue417.service` launcher stopped cleanly with exit status 0, its listeners
on 4000/4001/4050 closed, and the dedicated local `duris_issue417` database was
removed after a successful SQL dump. The dump includes all 281 base tables and the
view; its completion marker, gzip integrity and uncompressed SHA-256 were checked.
A new restore drill was not run for this cleanup.

The pre-retirement checkout, local news overlay, credentials, runtime, server
binaries and qualification evidence are preserved in a private, hash-verified
archive under
`/home/aiwithapex/.local/state/duris/setup-archives/2026-10-28-issue417-closeout/`.
Compiler objects and dependency caches are omitted. The archive's `RESTORE.txt`
records recovery instructions; its source is retained by the local
`archive/issue417-closeout-2026-10-28` Git reference. Do not publish the archive.

The main local server and `duris_dev` database remain in use. Redis database 0 and
the `duris:local:default` namespace are shared with the unfinished
character-mechanics checkout and were preserved. No production service or data
was changed by this retirement. The setup and execution details below are
historical, not instructions to recreate an active #417 environment automatically.

## Scope

[Issue #417](https://github.com/LuminariMUD/Duris/issues/417) owns the fresh,
end-to-end pwipe qualification on current master. This branch is the dedicated
workspace for its complete checklist and resulting fixes. This initial commit
records environment setup only; no destructive pwipe qualification or production
acceptance is claimed.

Related work: [wipe readiness #97](https://github.com/LuminariMUD/Duris/issues/97),
[prior qualification #264](https://github.com/LuminariMUD/Duris/issues/264),
[supervised reset and recovery #363](https://github.com/LuminariMUD/Duris/pull/363),
[writer-drain qualification #350](https://github.com/LuminariMUD/Duris/pull/350),
[Overlord recreation checkpoints #334](https://github.com/LuminariMUD/Duris/pull/334),
and [maintenance checkpoint archival #352](https://github.com/LuminariMUD/Duris/pull/352).

## Current qualification

The destructive full-world pass, discovered defects, fixes and final evidence are
recorded in [the qualification findings](issue-417-pwipe-qualification-findings.md).
The setup values below are the original baseline; the tested runtime now serves
season 4. Read the findings for the exact tested revision and remaining rollout
conditions.

## Workspace and custody

Prepared on 2026-10-27 from freshly fetched `origin/master` at
`151aaa23d520f4bdb2f78e7117f8cba4e0a54da7`.

- WSL path: `/home/aiwithapex/projects/duris-issue417-pwipe`.
- Windows path: `\\wsl.localhost\Ubuntu\home\aiwithapex\projects\duris-issue417-pwipe`.
- Published branch: `branch/issue-417-pwipe-qualification`.
- Source runtime: `/home/aiwithapex/projects/duris`, source checkout
  `ee24bc477fdbb0c53b27503b7243bf70727fbf3e`.
- Runtime role: `ENVIRONMENT=local`, `PERSISTENCE_MODE=mariadb-primary`.
- Database: `127.0.0.1:3306/duris_issue417`, copied from `duris_dev` after shutdown.
  All 281 base tables and 1,999,203 rows matched immediately after import; one view
  was also copied and checked for references to the source schema. No routines,
  triggers, or events were present. MariaDB version: `10.11.14`.
- Redis settings are identical to the source `.env`, including
  `127.0.0.1:6379`, database 0 and namespace `duris:local:default`.
- Loopback listeners: telnet `4000`, TLS telnet `4001`, WebSocket/HTTP health `4050`.
  The `--dev` launcher uses 4000; port 7777 is not needed for this instance.
- `.env` was copied with mode `0600`. The entire `lib/` folder, `runtime/`,
  `Accounts/`, `Players/`, `certs/`, and existing local backup data were copied.
  Source file contents were SHA-256 checked before boot. Both historical journals
  were preserved. Checkout-specific paths were redirected into this workspace.
- The copied source `lib/information/news` intentionally differs from newer master
  news. This is a local runtime overlay and is not part of this commit.
- Credentials, certificates, local configuration, database snapshots, transcripts,
  recovery journals, generated worlds and build outputs remain uncommitted.
  Additional runtime/backup exclusions live in the repository's local Git exclude
  file, not in the tracked project rules.

The original game shut down through its normal signal shutdown path with exit
status 0. Its `duris-mud.service` is inactive and disabled to prevent competing
startup. A transient user unit, `duris-issue417.service`, invokes this checkout's
`./scripts/start_mud.sh --dev` and keeps its launcher outside the tool shell.
It does not install a persistent boot service. Use
`systemctl --user stop duris-issue417.service` for a supervised graceful stop.
To start it after it has stopped, repeat the transient-unit command below; use
`systemctl --user reset-failed duris-issue417.service` first only if it failed.

```bash
cd /home/aiwithapex/projects/duris-issue417-pwipe
systemd-run --user --unit=duris-issue417 \
  --property=Type=forking --property=WorkingDirectory="$PWD" \
  --property=KillMode=mixed --property=TimeoutStopSec=90 \
  "$PWD/scripts/start_mud.sh" --dev
```

## Backups and validation

`PREBOOT_BACKUP=1` is enabled. The owner-only policy is
`runtime/backup-policy.local.json`; complete generations are under
`backups/issue417-generations`, with a separate restore-drill destination.
The policy uses the existing example's retention and capacity values, with
custodian `aiwithapex` and this checkout's authority/journal paths. The first
preboot generation completed and `./scripts/backup_pfiles.sh status` returned
`result=ok`. No scheduled timer, off-host replica, or restore drill is claimed.
The original SQL snapshot and setup evidence remain private under
`tmp/issue417-setup/` (directory mode `0700`).

Completed setup commands:

```bash
make -j2 BUILD_PROFILE=development PERSISTENCE_BACKEND=mariadb
make world
./scripts/cycle_mud.sh --dev --check-config
# With this checkout's protected environment loaded:
python3 scripts/migration_runner.py run
./migrations/verify_runtime_compatibility.sh
./scripts/start_mud.sh --dev
```

The build stamp is `mariadb/development`. Built/runtime executable SHA-256:
`3f20581941d4b602bc293576dfffdcd8bc337e5a3a11f5e1a67869b6933ff4f2`.
The migration runner and runtime schema checks passed against the clone; the
launcher repeats both gates before startup.

Live verification passed on all three listeners. `./scripts/healthcheck.sh`
returned success and `/health` returned
`{"status":"healthy","persistence":"ready"}`. TLS 1.3 validated against the
copied localhost certificate, and the WebSocket listener accepted an HTTP 101
upgrade with a configured Origin. The account and character configured in `.env`
logged in, ran `score`, received a successful `save` acknowledgement, and logged
out cleanly. The live process was checked for the new checkout, cloned database,
unchanged Redis configuration, redirected paths and expected binary hash.

Observed cold-boot wall time was approximately 241 seconds (23:13:50 to 23:17:51
Asia/Jerusalem), mostly before world loading while enumerating persisted item
population. Initial three-minute readiness probes expired while those SQL scans
were still advancing; health and login passed after boot completed. Preserve
this observation for #417's timing/capacity investigation. Mail recovery and
telemetry remain disabled by the copied local configuration.

Private evidence includes `clone-summary.json`, matching source/clone table
counts, the SQL snapshot, build/world/migration/compatibility logs,
`runtime-summary.json`, and `login-summary.json` plus the private transcript
under `tmp/issue417-setup/`.

## Qualification scope

The issue's live checklist is authoritative. The initial setup did not establish
the items below; the linked findings now record their executed scenarios, fixes,
evidence and rollout limitations:

- Reconcile reset/preservation coverage against current SQL, files, Redis and workers.
- Build synthetic old-season fixtures and prove an independent matched restore.
- Exercise authorization, cancellation, malformed requests and the real five-minute countdown.
- Verify fencing, quiescence, SQL/Redis/filesystem completion and explicit activation.
- Verify preserved account benefits, clean staff recreation and fresh identities.
- Play, save, reconnect and boot a second time in the fresh season.
- Inject failures and interruptions; prove safe refusal, retry and matched recovery.
- Exercise integration/configuration variants and flat-file refusal.
- Review operator messages, runbooks, timing and capacity.
- Publish revision-specific scenario evidence, defect dispositions and a readiness conclusion.

The user subsequently explicitly authorized destructive testing of this prepared
full-world worktree. Four real wipes used its cloned database and copied runtime;
controlled Redis/recovery variants and separate synthetic fixtures provided
additional coverage. The initial setup-only scope was
superseded by that authorization. The primary database was queried only as a
comparison reference. See the findings for actual tested revisions and scope,
and the [runbook](../operations/RUNBOOK.md),
[regression guidance](../testing/REGRESSIONS.md), and
[prior qualification plan](plan-issue-264.md) for supporting procedures.
