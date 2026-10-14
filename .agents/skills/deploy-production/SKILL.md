---
name: deploy-production
description: >-
  Update the native Duris production checkout from remote master, resolve Git
  conflicts, and prepare the production binary, online migrations, world,
  help, news, configuration, and jobs for the user's in-game reboot. Use when
  asked to deploy production or prepare its next release. Stop at the handoff;
  the user performs the reboot.
---

# Deploy Production

Prepare the complete release up to the point immediately before the user runs
the in-game **REBOOT**, then hand it back and stop. The normal command is
`shutdown reboot <reason>`; verify its syntax in the running version. Do not
substitute copyover unless the user requested it.

The reboot belongs to the user. This skill does not issue or schedule reboot,
copyover, or shutdown commands, stop or restart the MUD or website services, or
take over an outage. Do not ask for a maintenance window as the next step of this
workflow. A separate explicit request for maintenance establishes a different
task; a pending migration does not establish that request.

Run required migrations with the database, MUD and website online. A blanket
zero-client check or missing online runner option is a tooling limitation to
resolve, not evidence that the migration needs downtime. Follow the
[online migration procedure](references/maintenance.md) to assess the actual SQL
and, where needed, add a narrowly scoped online path to the runner.

A verified, fully prepared handoff completes this task; activation and its
verification are not prerequisites for finishing preparation. Carry the work
through that handoff without intermediate permission requests for already
authorized preparation. If a real prerequisite cannot be completed within this
boundary, finish the independent
preparation, report the exact unresolved requirement once, and stop. Do not call
the release ready for reboot while that requirement remains, bypass its guards,
or enter a repeated approval/polling loop.

All command paths below are relative to the repository root. Use the current
source and installed services as authority, not historical observations or fixed
migration numbers in documentation.

The sequence is: inspect and prepare the whole release, take a verified backup,
complete supported database and content publication, install the matching world
and next-boot binary, verify readiness, and hand the reboot to the user. Prepare
everything needed for publication before changing the live schema. The detailed
steps below follow that order.

## Keep deployment focused

Production deployment is an operational task. Do not turn it into a burn-in,
test-suite run, restore drill, infrastructure project, or unrelated cleanup.
Do not run regression suites, gameplay test servers, synthetic databases,
whole-tree formatting, security scans, or qualification journeys on production.
Those belong in a separately requested development or qualification task.

Use existing build and verification evidence for unchanged inputs. Build only
the required production artifacts, perform the short source/target checks below,
publish the prepared artifacts, and check the existing service's health. Missing
Docker, restore mounts, namespace permissions, an external validation host, or a
rehearsal receipt must never block deployment. A restore rehearsal is optional and
outside this workflow. Linked guides may describe broader maintenance or
qualification procedures; they do not expand this skill's pre-reboot boundary.
Do not provision testing infrastructure or repair unrelated tests during a deploy.

## Scope and authorization

An explicit request to run this deployment authorizes its ordinary production
preparation: backups, Git integration, builds, generated world/configuration
updates, required online database/content publication, and narrow runner fixes
needed to apply the reviewed migrations with services running. Reuse that
authorization; do not ask separately for each script's confirmation. Creating,
reviewing, or dry-running this skill is not authorization to deploy.

Use [the prerequisite handoff](references/maintenance.md) only for a demonstrated
constraint that cannot be resolved online, such as an incompatible writer or a
required new launcher. Name that constraint and the online approaches assessed;
do not hand back a migration merely because the existing runner demands stopped
clients. Keep the running services intact.

Deployment does not authorize player wipes, arbitrary historical repairs,
destructive content replacement, discarding local work, pushing Git history,
unrelated feature activation, or deploying DurisWeb's code. Account for its shared
database clients when identifying prerequisites. Preserve secrets, protected files,
and runtime state; change protected configuration only where this release needs
it, retaining private recovery copies and existing permissions. Missing credentials
or unclear balance choices need owner input, not invented values.

## 1. Establish the real starting state

Read `AGENTS.md`, the [production update inventory](../../../docs/operations/PRODUCTION_UPDATE_INVENTORY.md),
[host deployment record](../../../docs/operations/PRODUCTION_DEPLOYMENT.md), and
the starting/stopping, executable rollback, and migration sections of
[RUNBOOK.md](../../../docs/operations/RUNBOOK.md). Inventory every surface in the
update inventory; read its linked subsystem guides when that surface applies.

Inspect status, branch, remotes, local commits, dirty tracked files, and untracked
files before fetching. Resolve the intended remote master from this repository;
do not switch an unrelated checkout silently. Read only needed `.env` settings
without printing credentials. Record `ENVIRONMENT`, persistence mode, effective
DB host/port/socket/name and allow-list, Redis namespace, listener ownership,
service manager/scope, active launcher and server PID, enabled jobs, and health.
This host uses user units; a directory or account named `staging` is production
when `ENVIRONMENT=production`.

Record separately:

- Checkout HEAD, fetched master SHA, and the actually deployed source revision
  if it can be proved. Checkout HEAD is not proof of the running executable.
- SHA-256 of `/proc/<server-pid>/exe`, runtime and staged binaries, and their
  backend/profile stamps. Identify the server child, not just systemd's launcher.
- Live `mud_schema_baselines`, ordered `mud_schema_history` IDs/checksums,
  `mud_schema_migration_state`, and current runtime compatibility.
  `migration_runner.py inspect` is offline manifest
  inspection, not a query for pending production migrations.
- Existing world/config/content state, backup generation/contract, scheduled
  maintenance, and any previously staged release. Investigate a preexisting
  `dms_new` before replacing it or letting an unrelated restart promote it.

On a repeat run, reconcile the previous release evidence with the live process
and installed/staged hashes first. Reuse a verified candidate for unchanged
inputs. A newer `dms`, `dms_new`, or checkout does not prove activation. Preserve
a previously prepared release while its replacement is built separately. Before
changing live files, reconcile both `dms` and `dms_new` with the actual database
contract and intended next boot. Never restore the running binary merely because
it is still running: its startup contract may reject a schema already upgraded
during preparation. Recheck production state and backup freshness even when
reusing build evidence.

Use an owner-only uncommitted recovery directory outside `bin/` for deployed
executable bytes (`cp -L /proc/<pid>/exe ...`, regular-file and hash checks),
matching stamp, deployed schema manifest, configuration/content recovery copies,
and release evidence. Do not copy the proc symlink itself. Preserve the schema
contract that actually verifies the live DB; if HEAD already advanced, locate it
from a verified backup or reviewed prior revision. Do not fabricate a contract
or adopt a baseline to hide an existing mismatch.

## 2. Integrate master and account for the entire release

Fetch the intended remote master and pin its full SHA. Inspect all changes,
including deletions/renames, since the deployed revision, not merely the latest
pull. If that revision is unknown, reconcile actual artifacts, database history,
content, and configuration rather than declaring a docs-only pull a no-op.

Prefer a separate worktree for integration, build, and generation so a
crash cannot promote an unfinished live `bin/server/dms_new`. The release includes
reviewed production overrides. Keep independent user edits intact and out of
release commits; record the distinction between remote SHA, integration commit,
and intentional local deployment changes.

For a clean fast-forward, integrate the pinned commit with `git merge --ff-only
<pinned-sha>` (the pinned equivalent of a fast-forward pull). For local commits,
merge in the preparation worktree, preserving both histories. For overlapping
uncommitted edits, preserve the index/worktree and exact affected files before
resolving their three-way merge there. Carry nonoverlapping edits through. Never
use blanket `ours`/`theirs`, `reset --hard`, `clean`, force-push, or an unreviewed
stash-pop to make the tree appear deployable. Resolve conflicts from source
intent and verify the combined result; ask only when intent or data ownership
cannot be established. Do not commit unrelated user edits. Integration merge
commits may be needed; deployment does not otherwise imply commit or push.

Do not leave the live checkout mid-merge. Publish the already-resolved integration
and preserved edits after artifact checks and backup. Check for concurrent
edits before applying it. Reread changed deployment instructions, manifest and
script interfaces from the pinned release before executing them.

Keep a compact release checklist in the private evidence directory: each changed
or drifted surface, required action, verification result, and reason if inapplicable.
Use the inventory's full categories: server/schema; area tools/world/lookups;
help/news; properties/environment/features/dependencies; services/timers; backup;
seeds and conditional repairs. Investigate new scripts and migrations not yet
listed there. No category is complete just because a command exited zero.

Recheck remote master before publication. If it moved, review and integrate the
additional changes; with continuous movement report the exact verified cutoff
instead of claiming latest master. Reuse valid checks only for unchanged inputs.

## 3. Prepare the complete release outside live promotion paths

Build in the release workspace. Reuse a previously verified production artifact
when its source, configuration and dependencies are unchanged. Do not invoke
`make test-all`, `make test-db`, burn-in, or a substitute native test suite.
Existing unrelated test or formatting failures are follow-up work, not deployment
prerequisites. Do not wait for CI or start additional tests while waiting for input.
For a required online runner fix, run focused database-free checks of its guards
and execution path; do not point test harnesses at production.

```bash
python3 scripts/migration_runner.py inspect
python3 scripts/validate_runtime_compatibility.py
python3 scripts/epic_zone_seed.py check
python3 scripts/sync_race_innate_help.py --check
make -C src PERSISTENCE_BACKEND=mariadb BUILD_PROFILE=production
make -C areas/src
(cd areas && ./m_slow)
```

Require executable `bin/server/dms_new` and a stamp containing exactly
`mariadb/production` in the release workspace. Plain `make`, `make build-server`,
and `make test-db` stage development builds. `make build-production` uses `bin/server/production/dms_new`,
which is not the launcher's promotion path. Inspect dynamic-library requirements
on the target; build success elsewhere does not prove they are installed here.

Build area tools from the release source; reuse matching verified artifacts on
repeat runs. Existing executables alone do not prove their source. Regenerate
the entire world and all lookups for this release; copyover never runs the launcher's
`m_slow`. Verify all seven `areas/world.*` outputs and five `lib/misc/lookup*`
outputs named in the root Makefile, not just a generation stamp. Keep generated
files and compiled artifacts uncommitted. Generate callback labels into a checked
temporary file with `scripts/event_names.sh <release-binary>`; require nonempty,
valid output and record the binary hash it belongs to.

Review these together before declaring the release ready for the user's reboot:

- Pending immutable migration prefix, metadata changes and the target binary's
  runtime contract. Prepare an online runner invocation for step 4 using the
  [online migration procedure](references/maintenance.md). Assess compatibility
  with active writers and the target engine's DDL/locking behavior. Extend the
  runner for the reviewed pending steps when its existing online path is too
  narrow; retain target, backup, checksum, locking and ledger checks. Production
  boot verifies schema compatibility; it does not apply pending migrations.
- Durable object/world recovery and deleted or renumbered rooms/mobs. If copyover
  was explicitly requested, also compare the running writer's recovery format with
  the candidate reader, including struct/layout changes; a matching version
  integer alone is insufficient evidence.
- Changes to `.env.example`, properties, gameplay catalogs, feature switches,
  dependencies, service units, launcher, credentials and listener configuration.
  Trace whether they are read at boot, inherited in the process environment, or
  require a new supervisor/listener. An in-game reboot does not restart systemd
  or replace the existing launcher. Copyover also inherits descriptors and
  environment; `load_env_file()` uses `setenv(..., 0)` and cannot replace inherited
  values with edited `.env` values. Preserve existing feature choices and balance
  overrides while applying required additions and conversions.

Use the sibling [news-update skill](../news-update/SKILL.md) to audit missing
player-facing coverage and prepare `lib/information/news` through the pinned
release. Treat this as preparation until this deployment reaches publication;
override its standalone publication timing and do not follow newer remote
features into news without integrating them into the same release. Avoid duplicate
entries on repeat runs. Prepare and publish the final player-facing text once;
do not add temporary deployment/reboot notices or plan a second edit after
activation. Put activation status in the operator handoff and release evidence.
Include generated source edits in the release evidence.

Read [HELP_SYSTEM.md](../../../docs/content/HELP_SYSTEM.md). Reconcile imported
information and help with the final source, including `docs/lib/information/hints.txt`,
`lib/information/help_index`, and `help/duris_help_parsed.hlp`. Resolve source
precedence/colliding titles and missing or stale help for the deployed changes.
Run the innate help generator when its check demonstrates source drift, review
the generated diff, and rerun its check. A pull, build, or restart does not import
database content.

Audit epic-zone payouts when affected or missing; use `epic_zone_seed.py check`
and its `sql-audit` output with the [epic seed guide](../../../docs/operations/EPIC_ZONE_SEED.md).
`sql-apply --database ... --server-stopped` only generates SQL: prepare the reviewed
plan, but do not execute it against a running server or stop the server for it.
Report a required stopped-server seed as an unresolved prerequisite. Preserve
intentional overrides, including deliberate default-shaped exclusions. Do not
replay historical payout SQL or run all legacy repair tools as a post-pull checklist.

Before live publication, finish the content previews and review affected installed
units/jobs, backup policy, configuration and dependencies. Identify anything an
in-game reboot cannot activate. Resolve ordinary preparation failures within the
authorized scope; use the prerequisite reference only for a demonstrated remaining
constraint, not merely because a migration or service file changed.

Before DDL or other live mutation, confirm that every required next-boot
prerequisite can be completed with services running. If a known outage, unsupported
recovery format or missing required configuration prevents that, finish independent
preparation and report it before changing the live schema or dependent content.

## 4. Back up, apply migrations online, and publish content

Check scheduled reboots and concurrent staff activity without cancelling another
operator's schedule. Preserve recovery files and take a verified full backup with
`scripts/backup_pfiles.sh` **before** schema or content mutation. Select the contract
that verifies the database now; if the checkout's contract is newer, use the
preserved manifest through `RUNTIME_COMPATIBILITY_MANIFEST`. Check generation
metadata, file checksums and dump integrity. A restore drill is not required.

Before DDL, coordinate schema-aware backup jobs so none straddles the change.
Record any temporarily held backup schedules; leave MUD/website clients running.
Use the prepared release's runner and content sources with the verified production
configuration, checking each tool's resolved paths and database destination.

Apply the selected pending migrations through the reviewed online runner path
under the existing deployment authorization, keeping the database and its clients
running. If the live ledger already matches the candidate head, skip migration
application and verify compatibility directly. Follow
[the online migration procedure](references/maintenance.md) for exported configuration,
target confirmation, fresh backup and online-path requirements. Verify the ordered
history/state and run `migrations/verify_runtime_compatibility.sh` against the
candidate contract. An in-game reboot will not apply migrations for the user.

After a successful schema change, switch backup tooling to the new verified
contract, remove only deployment-owned temporary overrides and restore held
backup schedules. Keep the prepared publication moving: the still-running old
binary may reject the new schema on its next boot.

After backup and schema prerequisites, preview and publish with
`scripts/import_help_to_prod.sh --local --dry-run` then `--local` for the reviewed
bulk scope; use `--local --news-only --dry-run` then `--local --news-only` when
only news needs publication. If a bulk import already includes final news, do
not publish it twice. `--local` selects the configured production DB, not a dev
database. Answer the script's confirmation under existing deployment authorization
after checking its resolved destination. Never add `--clean` by default.

Compare live stored news bytes with the file and verify expected help/info rows
against the importer's actual transformations and precedence, not just row counts.
Review removed/renamed topics: an upsert does not delete obsolete rows. Reconcile
proven release-owned stale entries specifically; preserve production-authored
content and ask about uncertain ownership rather than clearing the table.
Retain recovery copies before replacement. Finish cache publication with `page`,
`page help`, and `page info` when authorized access is available; otherwise make
their boot refresh part of the reboot handoff. Help and info can become visible
through periodic refresh before reboot; if their new semantics cannot coexist
with the running release, prepare the import and list it as an unresolved
prerequisite instead of publishing incompatible content or stopping services.

Update affected installed user services/timers, backup policy integration,
login-statistics or enabled telemetry jobs using their owning guides. Preserve
host-specific paths, credentials, grants, and sandbox adaptations. Pulling a
template does not install it; use `systemd-analyze --user verify` and
`systemctl --user daemon-reload` as appropriate. Prepare required launcher/service
changes without restarting live services. If an in-game reboot cannot activate
them, state that exact prerequisite in the handoff. Do not run the dedicated-host
system installer over this host's user units.

## 5. Publish the prepared release without activating it

Require the live DB to pass the candidate's contract, supported world recovery,
and configuration/content that can take effect through the user's in-game reboot.
No required migration, stopped-server seed, or new-launcher prerequisite may
remain before staging a bootable candidate. Otherwise keep incompatible artifacts
outside live promotion paths and use [the prerequisite handoff](references/maintenance.md).

Use the verified pre-change backup from step 4; do not ask the old schema contract
to validate a database already upgraded to the new head. If safe publication
cannot be ensured while the game runs, report that constraint and keep incompatible
artifacts outside live promotion paths.

Publish the reviewed checkout/configuration, all seven compiled generators under
`bin/areas/tools/`, complete generated world/lookups, and matching callback map
with recoverable temporary-file replacements. Account for live readers and retain
prior bytes. Verify installed hashes against the release workspace. The launcher
rebuilds only missing generators, so stale tools can undo the prepared world at
the next boot.

Verify the deployed and candidate stamps both contain `mariadb/production`.
Inspect the actual launcher's promotion logic before choosing the final binary
path. In the current `cycle_mud.sh`, ordinary reboot returns 52 and executes
`bin/server/dms`; promotion from `dms_new` occurs only for 53/57, including the
initial launch's preset result. Staging `dms_new` alone does not prepare a new
binary for an ordinary `shutdown reboot`.

For the normal reboot handoff, after every prerequisite passes, install the
checked candidate at the next-boot `bin/server/dms` pathname by a same-filesystem
atomic rename from a temporary regular file, with its matching `.dms-backend`.
Preserve executable permissions and ownership, and verify the installed file is executable.
First preserve the running executable bytes and stamp outside `bin/`. Never copy
over or truncate the executable inode: atomic replacement leaves the existing
process running its old inode until the user reboots. Preserve and withdraw any
obsolete `dms_new` so a later launcher restart cannot promote a different release.
Verify separately that the installed `dms` hashes to the candidate and the same
running PID's `/proc/<pid>/exe` still hashes to the deployed binary.

If the user explicitly requested **copyover**, additionally require compatible
old-writer/new-reader recovery and inherited environment/listeners. The current
`copyover_save` renames `dms_new` directly to `dms` without the launcher's profile
gate, stamp move, world generation or callback-map generation. The retained runtime
stamp must describe the candidate, and the candidate's map must already be installed;
the old process keeps its map in memory. For this handoff, leave `dms` in place
and atomically publish the candidate to `bin/server/dms_new` last, with the checked
`.dms_new-backend` already installed. Check the running writer's connection
guards: TLS/WebSocket, login/account-menu or other non-playing descriptors can
cancel copyover, as can pending grants or failed persistence drains. Report these
conditions without disconnecting players, issuing copyover, or switching modes.

For either handoff, recheck process identity and installed hashes. Unexpected
activation invalidates the previous readiness checks. Leave activation to the user.

## 6. Prove readiness and hand off

After schema or content publication, take and verify a full backup under the new
live contract as well; retain the pre-change recovery generation. Recheck local
and public health, installed artifacts and the unchanged running process.

Before saying **ready for your in-game reboot**, require evidence for all of these:

- Pinned release integrated with all conflicts resolved; unrelated edits retained;
  no unaccounted required step in the release checklist.
- Verified backup/recovery files; new live runtime compatibility passes, and no
  pending immutable migration or required data operation remains.
- Candidate hash/stamp, matching callback map, generated world/lookups, production
  configuration preflight (`scripts/cycle_mud.sh --production --check-config`).
  This preflight is not a schema check; verify the live schema separately.
- Stored help/news/configuration/jobs match the reviewed release. Required cache
  reloads are done or explicitly supplied by the user's reboot.
- Existing production health is good (`scripts/healthcheck.sh`, correct user-unit
  logs, MUD/website endpoints), and preparation has left no service, client or
  schedule stopped or paused.

Report the verified remote/integration revision, candidate SHA-256, migrations
applied, content/world/configuration/job changes, backup location, checks and
remaining limitations. When ready, give `shutdown reboot <reason>` for the user
to run, or `shutdown copyover <reason>` only for an explicitly requested and
verified copyover. Say **preparation complete; activation remains with you** and
end the task. If tracking a goal, mark this preparation objective complete at the
verified handoff; do not label it paused or waiting for the user's reboot.
Close your own temporary sessions. Do not wait for activation,
request permission to do it, or continue polling because the user has not rebooted.

If a prerequisite remains, state **prepared, but not ready for reboot**, list the
exact unfinished operation and staged locations, and stop without offering to
take over maintenance. This is an incomplete readiness result, not proof that the
whole preparation objective was achieved. Optional qualification is never such a
prerequisite.

Live health before reboot proves the old process only. Verify activation only
in a follow-up when the user reports their reboot or explicitly asks for that
check: compare the running executable hash, stamp, callback map, schema and health,
and confirm any promotion expected for that path occurred. That follow-up is
outside this skill's pre-reboot completion boundary.
