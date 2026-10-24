# Operations Runbook

Day-to-day operation of a DurisMUD instance. First-time setup is in
[README.md](../../README.md).

For ordinary assisted production preparation, follow the
[`deploy-production` skill](../../.agents/skills/deploy-production/SKILL.md).
It completes the release with services running and hands the user the in-game
REBOOT command. The maintenance, qualification and stop/start procedures below
apply when separately requested; they do not extend that preparation task.

## Starting and stopping

```bash
./scripts/start_mud.sh     # preferred: systemd user service if installed,
                           # otherwise nohup cycle_mud.sh -> logs/duris-console.log
./scripts/cycle_mud.sh     # foreground supervised run (what start_mud wraps)
./scripts/cycle_mud.sh --dev   # development listener/build role on port 4000
./scripts/cycle_mud.sh --production  # require the production role on port 7777
./scripts/cycle_mud.sh --check-config  # validate the selected persistence mode only
```

Set `DURIS_DEV_PORT` to use a different development plain-telnet port when
another local service owns 4000. It accepts ports 1 through 65535 except the
production port 7777; the default remains 4000.

`cycle_mud.sh`:

- Anchors itself to the repository root; loads `.env` if present.
- Requires `ENVIRONMENT` in every mode. Database-backed modes also require `DB_HOST`,
  `DB_USER`, `DB_PASSWD`, `DB_NAME`, and `DB_ALLOWED_TARGETS`; `flatfile-primary`
  instead requires an absolute `FLATFILE_STATE_DIR`. It has no source-code credential
  fallback.
- Runs schema verification and MySQL shutdown logging only for a database-backed
  mode. Automatic migration application additionally requires `ENVIRONMENT=local`;
  production verifies the schema and does not migrate at boot. A `flatfile-primary`
  launch does not invoke those database tools, even when Redis is enabled.
- Raises core dump limits (`ulimit -c unlimited`).
- Rebuilds area tools and regenerates `areas/world.*` when the `make_*`
  helpers are missing.
- Regenerates `lib/misc/event_names` with `scripts/event_names.sh`: the
  executable's function names, local and weak ones included, which the event
  diagnostics use to name a callback.
- Promotes `bin/server/dms_new` to `bin/server/dms` only for result 53/57 (including
  the launcher's initial preset 53), retains the five newest
  prior executables under `bin/server/history/` by default, and runs the active
  binary in an outer loop. Set `DMS_BINARY_HISTORY_LIMIT` to change the limit.
  Ordinary in-game reboot returns 52 and executes the existing `dms` pathname;
  preparing that handoff requires installing the checked candidate there first.
  A `--production` launch promotes and runs nothing except a stamped
  `PERSISTENCE_BACKEND=mariadb BUILD_PROFILE=production` build: a staged binary
  with another stamp is logged and left in place, and the runtime binary keeps
  running. `make`, `make build-server` and `make test-db` stage a development
  build, so on a production host build the release after the tests, or restart
  before them. To run the database journeys against the production profile,
  `make build-production` and `DURIS_SERVER_BINARY=bin/server/production/dms_new
  make test-db`.
- On each restart it moves `logs/log/*`, `logs/player-log/*` and
  `logs/latency_trace.log` into `logs/old-logs/<timestamp>/`, then deletes the oldest
  archives until `logs/old-logs` fits in
  `DURIS_LOG_ARCHIVE_MB` (1024 by default; the newest is always kept). It writes the stop reason and optionally
  emails an alert. With `PREBOOT_BACKUP=1` it also runs `scripts/backup_pfiles.sh`
  before the boot, which publishes a verified full generation under the approved
  backup policy, and a backup failure then stops the cycle before restart. That is
  off by default: the backup timer takes the backups.
  Configure policy, scheduling, retention and isolated drills using
  [BACKUPS.md](BACKUPS.md) before deploying this launcher.

### Exit codes interpreted by the cycle loop

| Code | Meaning | Restarted? |
|------|---------|------------|
| 0 | clean shutdown | no |
| 52 | reboot | yes |
| 53 | copyover reboot | yes |
| 54 | auto reboot | yes |
| 55 | complete pwipe; explicit fresh start required | no |
| 56 | mud hung reboot | yes |
| 57 | auto reboot with copyover | yes |
| 58 | incomplete pwipe; operator recovery required | no |
| 139 | crash (SIGSEGV) | yes |
| 128 + N | killed by signal N, named: 137 is `killed by SIGKILL` | yes |
| other | unknown | yes |

Graceful shutdown from inside the game: immortal `shutdown` command
(`src/cmd/actwiz.c`). It writes `logs/shutdown_info.txt`
(`initiated_by|reason`), which `cycle_mud.sh` consumes for its reboot record
and then removes. Copyover (`copyover` command) execs a fresh binary while
keeping player connections alive via `copyover.dat`.

### Executable rollback and callback labels

Before an authorized clean build or rollout, identify the actual supervisor,
its system/user scope, and the executable behind the listener. A service name
or port alone does not establish environment role. Preserve the executable
bytes and matching backend/profile stamp outside `bin/`: `make clean-all`
removes `bin/`. The maintenance-scheduler state is under `runtime/` by default;
a `MAINTENANCE_STATE_FILE` that still points under `bin/` goes with it.

When copying `/proc/<pid>/exe`, dereference it into a regular file (for example,
`cp -L`), verify that the copy is not a symlink, and compare SHA-256 digests.
An archived proc symlink can hash correctly while the process lives and still
be useless after exit. Verify the running executable after promotion as well;
an ordinary in-game reboot is not proof that staged code was loaded.

Callback labels in `lib/misc/event_names` must match the loaded executable.
The launcher regenerates them with `scripts/event_names.sh`; an in-process code copyover
must also use a matching map. Stale addresses can invalidate callback-family
profiles even when the executable is correct. Follow the existing deployment
path and verify both identities before comparing profiles.

### Stopping a local instance

Use the same mode that started the instance:

```bash
# systemd user service, when installed
systemctl --user stop duris-mud.service

# foreground cycle_mud.sh session
Ctrl-C
```

For the fallback background mode started by `start_mud.sh`, use the in-game
immortal `shutdown` command when possible. The fallback does not create a PID
file; do not guess with a broad `kill` or `pkill` command. Check
`logs/duris-console.log`, the listener port, and the process command line before
stopping a specific local process. A normal shutdown lets the supervisor write
its reboot record and rotate logs.

### Production systemd service

The checked-in production unit is rendered from
`deploy/systemd/duris-mud-production.service.in`. It is a system service, so it starts
from `multi-user.target` without a login session or user lingering. It runs under the
checkout owner, sets `Restart=always`, disables systemd's restart-rate limit, waits ten
seconds between attempts, and invokes `cycle_mud.sh --production`. The launch flag
refuses `ENVIRONMENT=local`; the unit cannot silently publish a development role as
production. A deliberate `systemctl stop` remains stopped because systemd suppresses
restart jobs requested by the service manager. A stop or restart sends SIGTERM to the
launcher alone (`KillMode=mixed`): it passes the signal to the server, which shuts down in
order, records the stop in `server_reboots`, and exits without starting the server again.

Prepare the production `.env` and protected runtime directories before installation.
The service account must own `.env`, which must remain mode `0600`. Complete the
production checklist below, qualify migrations on a restored non-production clone,
apply approved migrations through the migration runbook, and run this offline preflight:

```bash
sudo -u DURIS_USER /absolute/path/to/duris/scripts/cycle_mud.sh \
  --production --check-config
```

> The production host (a shared Plesk host, user-scope account) does not use
> this system-wide installation: the MUD runs as the user unit
> `~/.config/systemd/user/duris-mud-production.service` (see
> `PRODUCTION_DEPLOYMENT.md`). The `sudo` steps below are the portable procedure
> for a host with a dedicated service account.

Install a disabled copy for inspection without disturbing the current listener:

```bash
sudo /absolute/path/to/duris/scripts/install-production-service.sh \
  --user DURIS_USER --no-enable
sudo systemctl cat duris-mud-production.service
```

The installer renders the absolute checkout path and account into
`/etc/systemd/system/duris-mud-production.service`, validates the unit with
`systemd-analyze verify` and reloads systemd. Enabling repeats the production
configuration preflight and refuses to proceed while another service owns port 7777.
The `--no-enable` staging path neither needs nor bypasses production credentials; the
service still enforces them whenever it is eventually started.

For the cutover, stop and disable any prior service that owns port 7777, then start the
production unit. Do not run the local and production units concurrently:

```bash
# If this checkout currently uses the local user service:
systemctl --user disable --now duris-mud.service

sudo /absolute/path/to/duris/scripts/install-production-service.sh \
  --user DURIS_USER --start
sudo systemctl status duris-mud-production.service
sudo journalctl -u duris-mud-production.service -f
```

Alternatively, `install-production-service.sh --start` performs enablement and startup
in one explicitly requested step. Installation does not create credentials, change
`.env`, run legacy migrations, or promote a database. A failed production preflight is
a deployment blocker, not a reason to weaken the unit or reuse development secrets.

Do not use `pwipe` for ordinary restarts. The full supported reset is still under
qualification in issue #264; this handoff repair alone is not wipe readiness.

Pwipe advances `season_reset_state.season_epoch` and records `resetting` before
destructive SQL. Startup refuses any non-active season. The singleton also holds
its handoff receipt: while `reset_status='resetting'`, a NULL `reset_completed_at`
means SQL/Redis/reward processing is incomplete; a non-NULL value means those stages
finished and filesystem cleanup remains. The launcher keeps status `resetting`
through cleanup, then atomically activates that exact epoch and records the final
completion time. Only then does it print `Wiped!`.

`shutdown pwipe` is unsupported in `flatfile-primary` and refuses immediately,
before scheduling a countdown or cancelling an existing reboot. The real client-free
server journey proves unchanged player snapshot/legacy files and continued save,
logout, reconnect and another boot. A MariaDB client binary refuses flatfile-primary
at startup; hybrid fallback mode is also rejected by existing configuration. This
is rejection qualification, not a successful flat-file wipe.

Reset policy confirmed by the owner for #264: every account-bank balance resets,
including staff and every racewar side. Bank rows are deleted without resetting
their allocator; accounts, credentials and donation history survive. Retained bank
ledger/baseline evidence keeps old bank IDs and cannot become a new bank's opening
balance. Only current exact level-62 Overlords are recreated under the same account
and name, with new PIDs, clean progression/currency, empty items/skills and fresh
opening baselines. Other characters and staff are retired. Their rows remain inactive
under reserved `~pwipe-PID` names, releasing ordinary names for the new season.
The roster change is one transaction: failure rolls back name/account/body changes
and retains the incomplete-reset fence. Old summon links are cleared every reset,
independently of the 28-day grant-decrement policy. Full staff login/gameplay proof
and persistent replay isolation are still issue #264 readiness gates.

Kingdom realms, purchased garrisons and legacy land ownership reset with guilds,
even if the optional kingdom feature is disabled. Association IDs can be reused;
retaining their old world rows would give a new guild the prior season's holdings.

Active Divine Boon objectives and their repeat-selection preferences retire at wipe.
The same versioned authority keeps its increasing boon-ID counter, bounded staff
history and pause/mode configuration. New-season objectives cannot reuse an old
cargo allowance's boon ID. Snapshot validation precedes the irreversible boundary;
a failed durable retirement leaves the reset fenced. Protected cargo receipts/books
are retained. The native reset journey proves committed receipt replay is inert,
and an unapplied pre-reset purchase is stale after ship deletion, including after
a same-named fresh mortal receives a higher-ID ship. Historical books/generation
remain unchanged; old wallet/cargo/market after-images do not return. Current boon
IDs are monotonic, so old books do not supply a new objective's allowance.

Auction custody payloads and siege items/affects/descriptions reset with the other
physical stores, including rows read by the startup artifact population scan. Their
separate audit ledgers, receipts and quarantine evidence survive. Quest trophies
remain character history; current gameplay does not consult their boot-loaded cache.

Artifact domain rows clear ownership, location, timers, souls and legacy custody
references. Canonical UIDs become retired (or absent when none existed), preserving
old-body rejection and allowing a fresh body through the existing creation path.
Rejected UIDs, delivery markers, baselines and immutable outcome/receipt history
survive; revision allocation continues from that history. Pending old deliveries
recognize the retired body and cannot feed or bind its replacement.

Collector candidates and held stock close through the normal audited season-reset
cancellation. Held items move to destroyed custody; listing records, payloads,
receipts and increasing listing IDs remain as history. Normal recovery excludes
terminal history belonging to retired characters, so it cannot fill the new catalog
or sell old stock. Preflight validates pending records/payloads after writer drain.
A failed cancellation leaves the reset fenced; retry skips already-closed listings.
The full existing runtime schema fingerprint is rechecked before the boundary,
including columns used by delegated ledger/custody writers.

Reward policy uses the durable reset start time and validates the current resetting
epoch. Grant changes and their policy timestamp commit together, so retrying an
unfinished reset cannot decrement grants again, even months later or after a lost
COMMIT acknowledgment. The existing 28-day protection between distinct resets is
preserved; eligibility is determined at each reset's start, not at retry time. Old
summon/body links are cleared even when that protection keeps the grants unchanged.

Before the boundary, the server checks `wipe_it_all --check` along with its existing
schema/Redis checks. Missing artifacts, unexpected store symlinks/types and denied
access abort before SQL reset. Cleanup revalidates the same fixed paths. Backups,
accounts and configuration are preserved; symlinks within a wiped store are removed
as links. This check covers the legacy stores handled by this script, not yet every
modern recovery store; the remaining inventory/isolation work is a readiness gate.

A successful SQL-stage server exits 55; an incomplete irreversible reset exits 58.
Exit 55 alone never authorizes deletion: the launcher checks its boot epoch's
successor and the durable SQL-ready receipt. Both terminal statuses propagate
through notifications; the systemd unit prevents restart on 55 and 58. Ordinary
reboots and crashes retain their restart policy. A crash during an incomplete reset
is stopped by the durable fence on the next launch.

The disposable runtime qualifier accepts `--redis --systemd` and an absolute
MariaDB production-profile binary path. It uses the production unit's sandbox and
restart settings with private identity/path, local configuration and the mini-world
launcher flag. It never starts the installed production unit. Native SQL dependency
checks separately exercise a real unavailable Redis endpoint and a denied cleanup
command: the first preserves the old season, the second keeps the new epoch fenced.
Repairing Redis cleanup alone does not declare SQL reset complete.

Before stopping website writers, complete DurisWeb's
[legacy temporary-copy preservation gate](https://github.com/LuminariMUD/DurisWeb/blob/7147e6b1bece2e650dbe3cb312c904edfa43bf9d/docs/deployment.md#legacy-temporary-copy-preservation-gate).
Its service's private temporary directory can be removed on stop. The player-event
season fence orders publication against the SQL boundary; the full external-writer,
cache, donation and reconnect cutover still needs its separate rehearsal.

Before scheduling a wipe, prepare and verify a **matched pre-wipe recovery point**.
The regular MariaDB backup contains SQL and journals; `PREBOOT_BACKUP=1` does not
add legacy filesystem or Redis coverage. After the website preservation gate above,
stop external seasonal/account-benefit writers and stop/drain the game. Freeze DDL
for the capture. With writers stopped, publish a verified SQL generation under the
approved policy, capture the data-root filesystem stores from the reset/retention
inventory (including wiped targets, accounts, bans, archives and configuration), and
capture Redis recovery data. Record the active SQL epoch/status, SQL generation and
manifest hash, filesystem archive hash, Redis capture hash, binary/world revision,
namespace and required configuration/key custody together. Store supplements beside
the SQL generation; do not modify its immutable manifest or files. Check age/capacity/
replica/drill status under [BACKUPS.md](BACKUPS.md); missing or mismatched supplements
mean the recovery preparation is incomplete. Keep external benefit writers stopped
until the reset/cutover is complete; restrict the resumed countdown to maintenance.

Rehearse restoration into fresh, isolated candidates before authorizing the wipe.
Verify every recorded hash and the matching active epoch before starting a candidate;
check current independent erasure/tombstone evidence. Use the existing private-DB
import and migration/value reconciliation, native journal verification, filesystem
copy and a separate Redis instance, then prove account login, saved items/balances,
world recovery and another boot. A full Redis RDB belongs only in a dedicated
candidate instance; never load it over shared live Redis or another application's
namespace. Use the matching runtime/configuration and world authentication key.
The optional `run_pwipe_runtime_journey.py --redis --restore` exercises this frozen
capture and isolated matched recovery with synthetic data. It does not promote a
candidate, install host backup policy or authorize a production restore.

After an interruption, stop the launcher/server and all external seasonal writers,
preserve logs and the matching DB/filesystem/Redis backup generation, and inspect
`SELECT season_epoch, reset_status, reset_started_at, reset_completed_at FROM
season_reset_state WHERE state_id=1`. For `resetting` with a non-NULL completion
timestamp, repair the filesystem problem and, with the same configuration, run
`./scripts/cycle_mud.sh --resume-pwipe EPOCH` (add `--dev` locally). It validates the
exact epoch, serializes cleanup, retries safely, activates only after successful
cleanup, and returns 55 without starting the game. Repeating it for that already
completed epoch does not delete new-season files. After an ambiguous activation
acknowledgment, read the row or repeat this same command; do not invent another epoch.

New reset epochs also record `roster_recreated` in the season singleton. Begin
sets it to 0; Overlord recreation and its 1 checkpoint commit in the same transaction.
New SQL-ready publication requires that committed checkpoint. NULL denotes legacy
or unknown provenance; the additive migration preserves it. Previously SQL-ready
legacy epochs can still use filesystem resume.

For `resetting` with NULL completion time and a known 0/1 roster checkpoint, use the
matching built native binary from the data root, with the original environment,
port and lifecycle configuration: `bin/server/dms_new --resume-pwipe EPOCH PORT`.
This SQL-only command acquires the normal runtime exclusion guard and verifies the
sealed schema and baselines before mutation. It refuses active/wrong/unknown epochs,
keeps the existing epoch and reset start, retries the reset body, skips a committed
roster, and targets the original Redis epoch. It starts no world, listeners or runtime
writers and does not clear filesystem data or activate the season. Exit 55 means SQL
is ready; run the existing launcher resume above to finish files and activation.
Exit 58 means recovery refused or remains incomplete; inspect `logs/log/status` and
`logs/log/debug`, repair the cause and repeat the same expected epoch. A second SQL
resume of a SQL-ready resetting epoch is read-only and also returns 55. It does not
reopen a completed active season. Keep all external writers stopped through both steps.

An unfinished legacy/unknown checkpoint cannot safely establish whether new staff
PIDs already committed. Use a matched pre-wipe DB/filesystem/Redis restore under
operator control for that case. Never infer a checkpoint or change the row to
`active` merely to bypass the fence. MariaDB generations made by
`persistence_backup.py` contain SQL and journals; filesystem and Redis recovery
evidence must be verified separately for a matched wipe restore. Full matched-restore,
carryover and integration qualification remain tracked in #264. Production reset,
recovery or restore requires owner authorization. Once the complete workflow is
qualified and the row is active, start the new season explicitly.

Every active Redis key and channel includes the boot-captured SQL season epoch. The old
process continues to target only the old epoch while pwipe is in progress; after restart,
the new process targets only the completed new epoch. Redis invalidation deletes and then
verifies the old epoch when Redis is enabled. If Redis is explicitly disabled, old keys
cannot become visible when it is enabled in a later season because no active unscoped
surface remains.

## Pre-service safety gate

Before a development start, confirm the intended role and target without printing
credentials:

```bash
# Validate mode-specific requirements without contacting a database.
./scripts/cycle_mud.sh --check-config

# Inspect names only. Do not print or copy secret values.
sed -n 's/^\(ENVIRONMENT\|PERSISTENCE_MODE\|FLATFILE_STATE_DIR\|DB_HOST\|DB_PORT\|DB_NAME\|DB_ALLOWED_TARGETS\)=.*/\1=<set>/p' .env

# Source-only contract checks; these do not connect to a configured database.
python3 tests/async/test_runtime_connection_trust.py
python3 tests/async/test_runtime_boot_compatibility.py
```

`DB_NAME` selects the database. `DB_ALLOWED_TARGETS` must explicitly allow that
name. The listener port is only a secondary safety guard: a non-production port
redirects a production-like name to the configured development target, but it is not
the primary database selector. A production role also requires the configured TLS CA
and a non-loopback database transport; a local/development/test role requires a
loopback target. The runtime applies a 10-second connection deadline before listeners
or persistence workers start and fails closed on identity, session-mode, schema, or
migration incompatibility.

Do not start the game if the target name, role, host, allow-list, TLS posture, or
backup status is uncertain. Qualify the exact target first; never probe a migration
script against a configured database to discover its command-line behavior.

### HTTP health probe

After startup, verify process and selected-persistence readiness without logging in:

```bash
scripts/healthcheck.sh
```

The probe needs the server's WebSocket and health listener, which is off unless
`DURIS_WEBSOCKET=TRUE`. It targets `http://127.0.0.1:4050/health` by default. For an isolated local
instance, set `DURIS_WEBSOCKET_PORT` on the server and the matching
`DURIS_HEALTH_URL` for the probe. A healthy response is HTTP 200 with only
`status=healthy` and `persistence=ready`; the handler performs no blocking
database round trip.

### Authenticated post-deployment smoke

When a deployment has been explicitly authorized for live validation, record
the current service PID/restart count, listener ownership, health result, and a
timestamp or cursor for each active log before connecting. Load the configured
`GAME_ACCOUNT_NAME`, `GAME_ACCOUNT_PASSWORD`, and
`GAME_ACCOUNT_CHARACTER_NAME` without putting their values in command
arguments, transcripts, or evidence files.

The client must accept both account-selection paths: a normal selection can ask
`Play as <character>?`, while reclaiming a link-dead character can enter the
game immediately. TLS can also reach the account prompt without the same
terminal preamble as plain telnet, and an SSL client must consume data already
buffered by the handshake. Treat prompts as states instead of sending the next
command after a fixed delay.

Use read-only gameplay commands such as `look`, `time`, `weather`, `score`,
`inventory`, `equipment`, `exits`, `who`, and permission-appropriate `users`.
Confirm the HTTP health probe still passes during the session, leave gameplay
with `quit`, select `0` at the account menu, and verify that no test session is
left attached or link-dead.

After logout, monitor the authoritative service journal and every current game
log through a quiet interval. Recheck the exact service PID/restart count,
listeners, health response, and absence of a new core file. Correlate expected
EOF, refused-connection, and orderly TLS-close messages with the smoke probes;
do not dismiss an uncorrelated persistence, crash, or integrity diagnostic as
test noise.

## Logs

All under `logs/`; each boot moves the last run's into `logs/old-logs/<timestamp>/` and keeps
the whole within the `DURIS_LOG_ARCHIVE_MB` cap. The hourly `address_retention` job also
moves the live logs there once they are a day old (the launcher marks a new set in
`logs/log/.since`; a set without the marker moves at the next run), and removes each archived file and
`core.*` dump 28 days after its last write: a file holds at most about 25 hours of lines,
so none of them reaches 30 days.

The logs hold players' names and network addresses. By
[ADR 0003](../adr/0003-player-privacy-chat-snoop-addresses.md) (2026-10-09), `logs/log/chat`
carries only petitions, immortal actions and the newbie channel, and `cmd.debug` keeps a
conversation command's word but not its text. The launcher keeps an archive at most 30
days, but the current run's logs stay until the next boot, so treat a copy of `logs/` as
player data.

| File | Content |
|------|---------|
| `logs/log/status` | Boot progress, MySQL connection status, system messages |
| `logs/log/syslog` | Game events |
| `logs/log/cmd.debug` | The last 500 player commands, written when the server exits or crashes; a say, tell or other conversation command keeps only its command word |
| `logs/log/wizlog` | Immortal commands |
| `logs/duris-console.log` | stdout/stderr of the supervised process |

In `flatfile-primary`, events sent through the database-backed audit logger remain
available in the ordinary files above: staff events use `logs/player-log/wizcmds`,
experience events use `logs/log/exp`, and player, quest, connection, and session events
use `logs/player-log/player`. Each entry retains its kind, player ID and name, IP, zone,
room, and message. Control characters are flattened so one event cannot forge another
log line.

Account password recovery by email writes to two of those files. At boot `logs/log/status`
carries the disposition: `Account recovery enabled (smtp port=<port> tls=<0|1>).` when
`MAIL_ENABLED=TRUE` and every `MAIL_*` setting validated, otherwise lines ending in
`password reset by email disabled.` that name the reason (`MAIL_ENABLED is not TRUE`,
`configuration rejected: <category>` where the category names the offending key, never its
value, or `mail sender failed to start`), followed by the boot sequence's own `Account
recovery unavailable; password reset by email disabled.` While the feature runs,
`logs/player-log/player` records one line per request, per completion, per mail result, and
when wrong guesses exhaust a code, carrying only the request id, the outcome category, and
the integer libcurl and SMTP codes (for example
`account recovery mail request=<id> outcome=<sent|retryable|terminal> curl=<n> smtp=<n>`);
`(account=redacted)` is literal. No line anywhere contains the reset code, the email
address, the account name, the client address, or libcurl error prose. Completions,
exhausted codes, save failures, and (rate-limited to one line per 60 s) terminal mail
failures or live-token evictions and host-window slot recycling also raise a `*** STATUS:`
notice to immortals watching status, which is mirrored into `logs/log/status`. A run of
terminal mail failures means the relay, its credentials, or its certificate chain is wrong:
fix the relay or `MAIL_*` settings and restart; never work around it by weakening TLS
verification, which the source contracts forbid.

Useful checks:

```bash
tail -f logs/log/status                 # boot + DB issues
rg 'NEVENT BUDGET WINDOW' logs/log/status # deferred and late events, a line per 75 s
rg 'telemetry_health' logs/log/status  # telemetry writer state and alerts
```

### Telemetry writer health

The game loop observes only the writer's cached atomic health; it never performs
SQL or waits for the telemetry worker. Each `telemetry_health` status line is
metadata-only and includes the backend/schema, producer and record sequence,
record kind, numeric error and failure class, queue/in-flight/retry state,
advisory-lock state, counters, and coverage gaps. It never includes a player
name, credentials, SQL text, or a record payload.

A retained record with no commit progress raises a warning after two configured
telemetry intervals and becomes critical after five minutes. An open circuit,
permanent repository failure, queue use at or above 80%, or a dropped control
record is critical immediately. Identical active failures produce at most one
reminder every five minutes, while state, severity, reason, and failure-signature
changes are logged immediately. An idle writer with no outstanding accepted
records does not become stale merely because it has no recent commit.

A writer refused at startup opens the circuit before any record is admitted, and
the line names the cause: `failure_class=permanent-schema` with `error=1146` and
`schema_check=table` for a missing table, `error=1054` and `schema_check=column`
for a column the writer needs and the table lacks, `error=0` and
`schema_check=column-type`, `index` or `engine` for a definition the check itself
refused, and `failure_class=permanent-permission error=1142` for a grant the
telemetry account lacks. The game runs on with telemetry off in every case.

A writer refused by its outage ledger says `failure_class=permanent-repository`
with `storage_check` naming the check and `error` the errno: `directory` (no
`TELEMETRY_OUTAGE_LEDGER_DIR`, a relative one, or this producer is already
registered; 22), `protection` (the directory or a file is not owned by the server
user with mode 0700 or 0600, or has a hard link; 1), `owner` (another process holds
`outages.owner`; 11), `ledger` (the ledger or a whole pending frame does not
decode; 74) and `io` (open, read, write, fsync or rename failed, for example 2 for
a missing directory or 28 for a full disk). A sample that cannot be written after
registration does not refuse anything; capture goes on and the ledger keeps its
last good sample.

A dependency that is down when the writer qualifies (a connection refused, the
advisory lock held, a lock wait past the two-second read timeout) is
`failure_class=transient-connection` or `transient-transaction` with
`state=degraded`, retried at a one-second cap for as long as it lasts; the line
shows `retry repository=<attempts>`. Only a permanent class opens the circuit.

A trusted operator can run `world telemetry` to inspect the same live metadata
without a debugger. Start with `state`, `reason_flags`, `failure class`, numeric
`error`, `schema_check`, `record_kinds`, `queue`, and `retry`; compare
`last_admitted_seq` with `last_committed_seq` to locate the unresolved range. Fix
the named schema, permission, connection, or storage fault rather than weakening
SQL/TLS policy.
A permanent open circuit retains its in-flight batch and requires the normal
reviewed telemetry lifecycle restart after the dependency is repaired. Recovery
is logged once, only after fresh commit progress, with the alert duration and
affected producer/sequence range.

### Command and event latency

Automatic 300-pulse windows go to `logs/latency_trace.log` only. Join command,
slow-tick, and scheduler records by boot ID, absolute tick, and monotonic
pulse-start time; each boot moves the previous trace file into
`logs/old-logs/<date>/`.
Worker samples render unavailable ticks as `-`. Window counts/min/max/means and
the exact bounded top ten describe that window, not process lifetime. Check
`dropped_section_samples`, `dropped_contended_samples`, and
`invalid_clock_samples` before interpreting an incomplete capture.

`COMMAND OP SLOW` and command-sweep reports start at 50,000 microseconds even
with debug profiling off. They distinguish playing, nanny, pager, editor, SSL,
and descriptor maintenance. `unattributed_sweep_us` covers work outside the
explicit scopes, including gates and dequeue. Playing labels use canonical
command names or `unknown`; arguments and nanny/editor input are excluded.
Reports retain at most eight slow operations and throttle output to one report
per four pulses, carrying suppression counts and the worst suppressed operation
into the next due report. A small event bucket does not explain a large command
bucket; a budget-exhausted event pass is not necessarily a 250 ms loop overrun.

For an authorized, bounded profiling capture, use `debug profile off`,
`debug profile reset`, `debug profile on`, then after the observation interval
`debug profile off` and `debug profile save`. These timers measure monotonic
elapsed work, including blocking time, not total process CPU. Compare callback
counts and per-call cost as well as totals. Nested scopes overlap and must not
be summed. The `nevent_defer_collect`, `nevent_defer_unlink`,
`nevent_defer_sort`, and `nevent_defer_merge` scopes isolate deferral phases;
`short_affect_liveness` measures the conditional owner-membership guard.
Verify profiling is off after capture.

`DURIS_NEVENT_TRACE_PLAYER=1` adds per-callback due/actual ticks, lateness,
sequence, and elapsed time to `logs/log/status`; `DURIS_NEVENT_ANALYTICS=1`
adds callback-family windows and the per-pulse `NEVENT BUDGET` and
`NEVENT CATCHUP` lines. These settings are cached after first use and
must be supplied to the process before use. Player traces contain player IDs:
keep raw captures private, bound their duration, and separate startup from
steady-state observations. The maximally late callback in a budget report is
not a complete count of late callbacks and may belong to an NPC.

For casting complaints, correlate a controlled mortal cast's intended duration,
callback timing, completion/abort, and queued input. Each segment of a cast is due at
the tick the one before it was due plus its own length, so a callback that ran late
shortens the next segment: a cast finishes at its cast time plus the lateness of its
last segment, or later only by the one-pulse minimum a segment keeps.
`tests/async/run_cast_timing_probe.py` measures this on a full-world flat-file server,
with `--budget-usec` to load the event pass. Aggregate scheduler samples alone do not
establish a particular player's delay or justify changing NPC cadence, priority
ordering, or budgets.

### Persistence health

A trusted character can run `world persistence` for a fresh, read-only view of
database and save health. Repeating the command takes new snapshots; it does not
cache output or mutate queue, Redis, deferred-save, or query state.

The report includes up to eight deterministically ranked query source sites,
total calls and failures, registry overflow, the persistence writer's queue, bytes,
age, retries and failures, dirty and deferred player saves, world capture
and publication health, redacted shared Redis boot/recovery/maintenance calls, failures,
timeouts, maximum latency and reconnect transitions, per-worker Redis operation latency,
failure streak, and last-success age, critical-command queue and fence health, flat
shop materialization event/byte capacity and reclaimable counts, and the oldest aggregate
save age. Output is metadata-only and
must not be copied into a workflow that expects SQL, player, account, item, IP, or path
values.

Interpret explicit states as follows:

- `state=empty` means the observed subsystem currently has no pending work or
  has recorded no query calls.
- `state=disabled` means the reported optional backend or integration is configured off.
- `state=unavailable` means the subsystem is enabled but its local health state
  cannot currently confirm availability. `heartbeat=unavailable` means that
  queue worker has never published a heartbeat.
- Failed deferred work normally remains in `scheduled` while its bounded retry is
  pending. `failed_unscheduled` should remain zero; a non-zero value means scheduling
  invariants were violated and requires investigation.
- `registry_overflow` greater than zero means additional source sites were not
  retained; recorded totals remain bounded and should not be treated as a full
  site inventory.

The displayed query operation IDs and any `SQL_TRACE` operation IDs are scoped
to the current process. They are correlation aids, not durable transaction or
idempotency identifiers.

For `writer` and `critical_commands`, a growing `oldest_age_ms` with rising
`connection_retries` or `retries` means the database is unreachable: the writer keeps
that job at the head of its queue and the game carries on. Restore the database. Nothing
is journaled, so a crash before then loses what was queued. `failures` counts jobs
dropped on any other error; their owners are marked dirty and saved again. See
[PLAYER_SAVE_PIPELINE.md](../persistence/PLAYER_SAVE_PIPELINE.md) and
[CRITICAL_COMMAND_PIPELINE.md](../persistence/CRITICAL_COMMAND_PIPELINE.md).

For `critical_outbox`, pending age may briefly rise during destination recovery.
`boon_rewards` counts checks filtered before operation-ID allocation separately
from accepted submissions and completions. Definition refresh failures reduce the
optimization, not reward eligibility: unavailable or 60-second-old views fall
back to the authoritative writer. Definition creation/reactivation invalidates
on admission and writer retries; removal, expiry and completion also invalidate.
Zero-entry accepted SQL results retain a versioned canonical receipt with an
explicit zero-event expectation, while old 2,080-byte receipts remain readable.
`critical_outbox_health` reports operational counts and the historical audit
separately: `unavailable` means no successful refresh yet, `stale` means a failed
refresh or an overdue observation, and `fresh` includes the age of the last good
sample. Operational counts refresh with the 250 ms delivery loop; the historical
audit runs after delivery, initially and then 60 seconds after each attempt.
`state=unknown` must not be interpreted as an empty queue. Lifecycle drains use a
new worker observation rather than these diagnostic counts, and allow the normal
game-thread outbox publishers to progress within the existing caller deadline.
`dead_letter>0`, `incomplete_inbox>0`, or `outbox_mismatches>0` is an integrity
incident. The last counter counts committed operations whose expected event set
differs from the actual set, including partial loss, wrong indexes, and unexpected
events for a zero-effect operation. Preserve the database rows, stop affected
domain cutovers, and run the typed reconciliation report.

`state=reconciliation` and `unknown_expectations>0` mean some historical event
sets cannot yet be proven. `reconciliation_candidates` is the subset without any
outbox row; it is a candidate count, not proof of loss. An old multi-event
operation can remain unknown even with a surviving event. Investigate that
coverage rather than assuming zero or declaring the audit clean. The audit scans
all committed history on each scheduled attempt. Session audits require their
typed receipt to prove an omission; combat children require the exact derived
parent/participant identity, hashes, ledger revision/delta, reason, and source.
New operations record their expected event count atomically. No-op/rejected
operations can expect zero; recovered stone receipts still expect their event.
Never backfill unknown expectations from surviving outbox rows, subtract a fixed
candidate count, delete evidence, or manufacture events to make the display green.

After correcting the destination, retry only the
specific numeric dead-letter ID through the guarded repair API; never edit payloads or
execute SQL copied from a command.

For `shop_materialization`, `state=degraded` means the checksummed catalog has reached
80% of its event or byte limit. `state=unavailable` means its lock, read, checksum, or
bounded decode failed. Preserve the authority files and transaction journal, stop new
flat-primary shop trades, and investigate the storage or catalog before attempting any
repair. The health read is lock-scoped and on demand; it never prints player, item, or
path data.

### Save alerts

`deferred_save_retry_scheduled` means the live character remains the recovery source;
the alert includes only delay and aggregate counters. Let the bounded retry run and
watch `world persistence` for pending age and failure growth.

Camp, rent, death cleanup and ghost extraction never keep a character for its save. A
`terminal` alert with `queue_failed` means a leaving character's save could not be
queued; the character left anyway and its state since the last written save is lost.
`terminal_save_failed` with `extract_refused=1` means an offline artifact transition
could not queue the owner's save and kept the offline owner; retry the artifact action.

`terminal_not_durable` with `leave_vetoed=1` means the locker could not be prepared for
saving in memory. The occupant and dynamic locker room remain live; do not purge either.
Check the locker log and have the occupant retry departure.

A copyover alert with `copyover_cancelled=1` means the writer could not drain within 30
seconds and the process returned to the live game loop. No fallback restart should be
forced. Correct the database failure, confirm the writer's age is falling, then request
the copyover again. Shutdown alerts carry `shutdown_cancelled=0`: shutdown went ahead,
and the log names any save it could not write.

## Restart and crash recovery

The automatic recovery paths are:

1. **Redis world-state recovery** -- after either a graceful restart or an unclean exit,
   the current immutable generation is accepted only
   if schema, completeness, sequence, checksum, size, and age validate. Floor deltas are
   decoded with the matching generation into one semantic plan. Every custody-bearing
   item in each bounded tree must exactly match SQL UID, root, parent, room owner, VNUM,
   and active state before rollback-capable materialization. Authenticated reconstructible
   world-pop objects have no SQL custody, player corpses use their separate restore path,
   and NPC-held items are not recreated. The
   exact restored generation is then consumed. A fenced one-use marker distinguishes
   clean restart from crash recovery.
2. **Copyover recovery** -- only with `-C` boot flag / copyover flow.

If Redis recovery fails, the server runs a full normal reset for every zone. Check
`logs/log/status` for `Performing redis clean restart recovery...` or
`Performing redis crash recovery...` followed by `applying full normal zone boot`, and
verify player integrity before reopening. The rejected generation and floor data are not
cleared by the failed restore.

For queue or dependency incidents, use `world persistence` and the detailed `redis`
status command. Do not clear a player save queue: player state is owned by memory and
the persistence writer's queue, not a Redis dirty set. A world generation publish
failure preserves the prior current generation and retains floor deltas for retry.
A `domain=world_recovery` alert means three capture attempts in a row left no generation:
its action is the reason and its detail the age of the last good one
([CONFIGURATION.md](CONFIGURATION.md)). Captures resume by themselves once the cause is
gone; no restart is needed.

Account password recovery keeps no durable state. Reset codes, their per-account cooldown
records, and any queued or in-flight recovery mail live only in process memory, so a
copyover or restart discards them; the player-facing text already says to request a new
code after a restart, and no operator action or cleanup is needed. The mail worker is not
part of the shutdown drain chain, so a dead or slow relay can never delay or cancel a
copyover or shutdown. The worker thread is joined at shutdown, though: when a send is in
flight at the moment `SIGTERM` arrives, process exit may take up to 20 s longer (libcurl is
bounded to 10 s connect / 20 s total per send, with no retry). The production unit's
`TimeoutStopSec` must stay above that tail; the checked-in
`deploy/systemd/duris-mud-production.service.in` uses 90 s. `scripts/change_password.sh`
remains the operator fallback for an account with no usable email address on file.

### Known-benign log lines

These are investigated and understood; they are not signs of a failed boot.

| Line | Meaning |
|---|---|
| `Heaven has invalid number: 1 (should be 0)` | `recalc_zone_numbers()` finding and correcting a zone number that disagrees with its lowest room vnum. Self-healing; fixing the data would be zone-numbering surgery with a wide blast radius. |
| `PERSISTENCE: worker_unavailable_flat_fallback` (a few lines at boot) | Item events fired during world load are written to the flat fallback and replayed before the workers start -- followed by `replayed N fallback persistence events; 0 remain queued`. Working as designed. |
| Mob log `RIDICULOUS damage` / `M cmd not executed` | Area data, not engine defects. `M cmd not executed` is a rare load's chance roll missing: a load under 100% is rolled only by the boot's forced reset, as the `Rareload` help says, so these lines come only at boot. |
| Debug log `a pitiful slave (19953) got 1500p from room.`, twice per boot | Intended (owner decision, 2026-10-09). The slave, mob 19617, loads in room 19624 and wanders into the Vault of Avernus (room 19953), where it picks up the two coin piles the zone loads there; killing it gets them back. |

## Backups and maintenance scripts

| Script | Purpose |
|--------|---------|
| `scripts/backup_pfiles.sh` | Publish verified full generations under the approved policy; also gates each cycle iteration. |
| `scripts/restore_flatfile_backup.sh` | Qualify a flat-file generation in a fresh isolated candidate with current erasure evidence. |
| `scripts/delete_corpses.sh` | Retired safety stub; exits nonzero without reading or changing MySQL or Redis. |
| `scripts/clear-redis.sh` | With the game stopped, use the scoped maintenance ACL identity to delete only the configured `REDIS_NAMESPACE`, legacy `mud:*`, and retired `ship:snapshot:*` keys from an explicitly confirmed, local, allow-listed Redis target; unrelated keys are preserved. |
| `scripts/import_help_to_prod.sh` | Import help sources to MySQL; use `--dry-run` first and treat `--clean` as destructive. |
| `scripts/migrate_players_to_accounts.sh`, `scripts/convert_all_pfiles.sh` | One-shot legacy data conversions; back up and review their assumptions before use. |
| `bin/migrations/*` | Offline pfile/schema conversion binaries built from `migrations/tools/`. |

Migration qualification follows the isolation rules in
[DATABASE.md](../reference/DATABASE.md): preserve the backup and validate replay
on a clone, never against live data. For authorized production application,
select the supported online or stopped-client path in the procedure below.

Full backup policy, generation format, journal consistency, retention,
separate/off-host custody, erasure preflight, isolated restore qualification and
operator cutover/rollback are maintained in [BACKUPS.md](BACKUPS.md).
BACKUP_POLICY_FILE is mandatory; legacy per-mode backup-root variables and the
old raw-copy restore interface no longer select or bypass the policy.

### Migration procedure

For routine pre-reboot preparation, first check the runner's supported online
paths in [IMMUTABLE_MIGRATIONS.md](../persistence/IMMUTABLE_MIGRATIONS.md).
The reviewed `run --online-level-cap-sides` path permits only the exact sealed
0039 addition on MariaDB 11.8/InnoDB, with a fresh verified backup, compatible
running writers, coordinated backup jobs and the runner's locking/DDL guards.
An authorized deploy completes that supported path without stopping services.
The remaining procedure below covers isolated qualification and a separately
authorized stopped-client rollout; clone qualification is not a requirement of
the deployment skill's pre-reboot handoff.

All migration qualification is offline work on a disposable database or a restored,
backed-up development clone. Stop every writer before cloning. Record the source
backup identity, restore it under an explicitly non-production name on a loopback
host, and set `ENVIRONMENT`, `DB_HOST`, `DB_NAME`, and `DB_ALLOWED_TARGETS` so the
clone is the only permitted target. Keep the original backup untouched.

Before converting locker authority to flat files, run the read-only, aggregate-only
`migrations/check_flatfile_account_locker_conversion.sh --expect-count <known-count>`
against that clone. It proves each `account.<account>.<side>.locker` row maps to an
authoritative account and valid racewar side, and checks owner fields, chests, item
custody identifiers, duplicate active UIDs, and access references. Quarantined or
otherwise inactive legacy payload rows are outside this authority conversion and remain
subject to their separate recovery workflow. Any nonzero mismatch or unexpected total
blocks the cutover; the checker never emits account or locker names.

The legacy runner is mutation-capable and has no dry-run mode. `--help` is safe, and an
unknown argument is rejected before configuration is loaded. A normal no-argument run
begins work immediately. When `REDIS=TRUE`, its final step requires `ENVIRONMENT=local`,
an exact `REDIS_HOST:REDIS_PORT/REDIS_DB` or `unix:REDIS_SOCKET/REDIS_DB` entry in
`REDIS_ALLOWED_TARGETS`, and the configured ACL/TLS settings. It deletes only
`<REDIS_NAMESPACE>:*`, legacy `mud:*`, and
retired `ship:snapshot:*` keys, verifies
the postcondition, and fails the migration if `redis-cli`, the connection, deletion, or
postflight fails. When Redis is disabled, the step reports `not enabled` without requiring
Redis connection fields. The game and every other Redis writer must remain stopped.

Production runtime startup requires distinct `REDIS_WORLD_*`, `REDIS_PRESENCE_*`,
`REDIS_CACHE_*`, and `REDIS_MAINTENANCE_*` credential pairs, plus a distinct
`REDIS_DONATION_*` pair when donation subscription is enabled. Do not temporarily reuse a
runtime identity for maintenance: correct the ACL configuration and repeat preflight.
Local maintenance may fall back to `REDIS_USERNAME`/`REDIS_PASSWORD`, but an explicitly
configured maintenance pair must be complete. Rotate one subsystem at a time by updating
that Redis ACL user and its matching environment pair, then restart; connection settings
are boot-captured and credentials are never reread on a gameplay path.

World recovery requires an independent `REDIS_WORLD_STATE_SECRET`. To rotate it without
accepting unsigned data, move the old value to `REDIS_WORLD_STATE_SECRET_PREVIOUS`, install
the new current value, restart, and wait for a new acknowledged generation. Then remove the
previous value and restart again. A manifest signed by neither key, or a generation whose
SHA-256 digest differs from its authenticated manifest, is rejected before materialization.

On the qualified clone only, use this order:

```bash
# 1. Legacy additive upgrade and exact verified adoption. No arguments; mutates immediately.
MIGRATION_ENV_FILE=/path/to/owner-readable-clone.env ./migrations/run_migration.sh

# 2. Inspect the checked-in manifest identity without opening the database.
python3 scripts/migration_runner.py inspect

# 3. Apply the immutable post-baseline prefix and verify boot compatibility.
python3 scripts/migration_runner.py run
./migrations/verify_runtime_compatibility.sh
```

For the separately authorized stopped-client rollout described here, after that
exact backup has passed on the clone, apply only the immutable pending prefix.
Keep every production writer stopped, create a fresh
backup with `scripts/backup_pfiles.sh`, and pass both the resolved target and backup explicitly:

```bash
set -a
source .env
set +a
python3 scripts/migration_runner.py run \
  --confirm-production-target "$DB_HOST/$DB_NAME" \
  --production-backup /absolute/path/to/fresh-production.sql.gz
./migrations/verify_runtime_compatibility.sh
```

The default production path refuses baseline adoption and legacy migration. It requires
`ENVIRONMENT=production`, an exact `DB_ALLOWED_TARGETS` match, a backup no more than two hours old
that is an owner-only regular gzip containing the configured Duris schema, CA-verified TLS for a
remote database, and zero other connections to the target before it applies each step.
The reviewed online path retains the target, backup, ledger and verification guards
while allowing live clients under its specific constraints. Do not bypass those
guards. Preserve the backup through deployment and the final soak.

Keep the clone configuration separate from the server's `.env`; the legacy runner
loads the file named by `MIGRATION_ENV_FILE` and rejects symlinks, non-regular files,
and files readable by group or others. That file must describe the allow-listed
loopback clone and must not contain production credentials.

For a fresh disposable bootstrap, import `migrations/bootstrap_multithread_safe.sql`
and use `adopt --kind fresh_bootstrap` instead. Without the two explicit production arguments, the
immutable runner rejects production roles, non-loopback hosts, production-like names, manifest
drift, incomplete baselines, or broken history. The compatibility verifier is read-only but
database-connected and must receive the intended target. Never use production for migration
discovery, qualification, or exploratory replay. The guarded immutable application and its final
read-only compatibility verification are the only production steps in this procedure.

If this stopped-client procedure fails, keep writers stopped and preserve the database, command output,
manifest, and backup. Do not edit ledger rows, skip a verifier, rerun a partial legacy
bundle blindly, or guess a reverse DDL. MySQL DDL may already have committed. Recovery
is to investigate on another clone or discard the failed clone and restore the known
backup, then repeat the entire qualification. See
[IMMUTABLE_MIGRATIONS.md](../persistence/IMMUTABLE_MIGRATIONS.md) and
[RUNTIME_COMPATIBILITY.md](../persistence/RUNTIME_COMPATIBILITY.md).

### Domain reconciliation

The reconciliation scripts below are read-only reports, but they connect to the
selected database. Run them only after repeating the exact clone target qualification
above; never use production as a development or validation target.

```bash
./migrations/reconcile_auction_transactions.sh
./migrations/reconcile_artifact_guild_outcomes.sh
./migrations/reconcile_boon_reward_zone.sh
./migrations/reconcile_phase02_domains.sh
```

Wallets, banks, epic points, frags and item ownership are saved from memory since the
[persistence reset](../adr/0002-persistence-reset-memory-is-the-authority.md): a save writes balances
without a ledger row and claims the items it holds without a transfer, so no ledger
explains them and no reconciler checks them. `item_owner_audit` records each item a save
took from another owner, and `logs/log/dupes` each item a save or load gave up.

A nonzero mismatch is an integrity incident, not permission to edit current rows.
Stop the affected domain, preserve its inbox, outbox, ledger, and report,
then trace the stable operation identity. Use only the domain's guarded retry or
repair interface after the cause is known.

For character-baseline readiness, `migrations/check_character_baseline_readiness.sh`
is production-safe and aggregate-only. It requires every active, unblocked,
account-mapped character to have wallet, epic, and combat-frag opening rows. The same
gate runs during MariaDB boot, runtime compatibility verification, and guarded legacy
dump import; a missing row makes the character generation unready.

Classify missing combat baselines only at an approved quiesced save boundary. Create a
private operator directory, then write the row-level result there; routine output stays
aggregate-only:

```bash
install -d -m 700 /absolute/private/combat-baseline-review
./migrations/repair_missing_combat_baselines.sh \
  --classify /absolute/private/combat-baseline-review/classification.tsv
```

`safe_no_history` has revision zero and no ledger row, so its opening value is the
locked current value at revision zero. `ledger_history_requires_review` includes only a
proposed arithmetic candidate and is never applied by the tool; prove the complete,
contiguous history and review separate targeted DML. `revision_without_ledger` has no
defensible automated opening value. Keep all PIDs and row details in the owner-only
artifact. Classification is not a resolution: every non-safe row requires a separate,
owner-only per-PID decision record containing the frozen source evidence, authoritative
opening value and revision, reviewed DML checksum, reviewer identity, and either an
explicit approval or `blocked_no_authoritative_opening`. The repair tool deliberately
does not consume those records. Do not mark the production incident resolved until every
affected row has an approved disposition and the aggregate readiness gate is zero.

Rehearse safe rows only on a fresh production clone after a verified backup and with
all writers stopped. Supply the reviewed artifact digest and backup identity:

```bash
WRITERS_QUIESCED=TRUE COMBAT_BASELINE_BACKUP_ID='<backup-generation>' \
  COMBAT_BASELINE_ROLLBACK_EVIDENCE=/absolute/private/combat-baseline-review/rollback.sql \
  COMBAT_BASELINE_ROLLBACK_SHA256='<reviewed-sha256>' \
  ./migrations/repair_missing_combat_baselines.sh --apply \
  /absolute/private/combat-baseline-review/classification.tsv '<sha256>'
```

The insert-only transaction preserves existing baselines, verifies locked player and
ledger state, fails on a conflicting baseline, and rolls back unless character readiness,
wallet, bank and epic baseline coverage, and the required foreign keys all pass. Balances
are saved from memory without ledger rows, so it does not compare them with the ledgers.
It writes those aggregate results to an owner-only receipt. The required rollback file
must contain reviewed inverse DML limited to the artifact's exact PIDs, values, and
revisions, with guards rejecting any subsequent combat revision or ledger activity. A
repeat is idempotent only when the existing row exactly matches the reviewed opening.
This command refuses production targets; it is rehearsal evidence, not permission to
repair production. Before any separately authorized production repair, retain the
backup, protected per-PID decisions, reviewed forward and rollback DML, all digests, and
the rehearsal receipt. Afterwards rerun the same checks. Never delete
or rewrite ledger history to make readiness pass.

Loopback combat-baseline clone targets are permitted directly. A remote clone additionally
requires verified TLS and an exact port-aware `DB_ALLOWED_TARGETS` entry in the form
`host:port/database`; a non-default port cannot reuse authority granted to another endpoint.

For the physical-coin replacement signature, first stop all writers at a clean save
boundary and create a private operator directory. Classification writes the exact
row-level old-custody/new-payload pair only to that directory; routine output contains
only a count and digest:

```bash
install -d -m 700 /absolute/private/coin-custody-review
./migrations/reconcile_coin_custody_pair.sh --classify \
  /absolute/private/coin-custody-review/pair.tsv
```

Review the protected artifact against the backup and frozen reference. It is eligible
only when there is exactly one canonical money payload without custody and one matching
active, baselined player-custody row without any payload, with the same player, vnum, and
container parent. Never infer a second pile from currency totals and never delete the old
custody history.

Rehearse only on a fresh non-production clone. The guarded transaction restores the
payload's UID to the still-authoritative custody identity; it does not alter denominations,
wallets, baselines, owner revisions, or ledger rows. Apply first proves that the database
rejects an invalid temporary-table `CHECK`; it aborts without DML or a receipt when that
guard is disabled or cannot be verified. Name the clone exactly `duris_dev`, `duris_local`,
or `duris_test`. Every coin-custody apply, including loopback, also requires an exact
port-aware `DB_ALLOWED_TARGETS` entry in the form `host:port/database`:

```bash
WRITERS_QUIESCED=TRUE COIN_CUSTODY_BACKUP_ID='<backup-generation>' \
  ./migrations/reconcile_coin_custody_pair.sh --apply \
  /absolute/private/coin-custody-review/pair.tsv '<sha256>'
```

Preserve the owner-only receipt and rollback evidence. Before any separately authorized
production repair, prove the same preconditions under row locks, retain reviewed DML and
the exact backup, and run the player materializer plus schema and FK reconciliation on
the clone. Rollback is the inverse UID update to the exact payload
row and is safe only before the repaired player is loaded or saved again.

### Maintenance, lifecycle, export, and erasure

The maintenance scheduler is bounded and persistent. Use `world persistence` to
inspect slot state, lag, errors, and deferred work. A disabled lifecycle slot is the
expected checked-in state, not a fault. Do not enable it by editing state files. The
`address_retention` slot runs hourly and clears network addresses 30 days after their
last use (ADR 0003), in the database and in the log files (see Logs); its first run on an
old database takes many short runs.

These commands are local inspection or source-contract checks and do not connect to
the configured database:

```bash
python3 scripts/lifecycle_archive.py inspect
python3 scripts/lifecycle_archive.py plan \
  --store database:accounts --action archive \
  --cutoff 2025-01-01T00:00:00Z --upper-bound 999
python3 scripts/personal_data_export.py inspect
python3 scripts/account_erasure.py inspect
python3 scripts/validate_data_lifecycle.py --json
python3 tests/async/test_data_lifecycle_manifest.py
```

Under the checked-in policy, archive planning reports blocked, export and erasure
inspection report `blocked_by_policy`, and canonical mutation remains disabled. These
are engineering controls, not controller approval. They are not a claim of legal
compliance. Do not invent policy references, selectors, retention periods,
shared-record decisions, or destructive adapters. Follow
[DATA_LIFECYCLE.md](../persistence/DATA_LIFECYCLE.md),
[LIFECYCLE_ARCHIVE.md](../persistence/LIFECYCLE_ARCHIVE.md),
[PERSONAL_DATA_EXPORT.md](../persistence/PERSONAL_DATA_EXPORT.md), and
[ACCOUNT_ERASURE.md](../persistence/ACCOUNT_ERASURE.md).

### Restore and tombstone preflight

Never reopen a restored environment immediately. Keep listeners, login, replay,
imports, cache publication, and export release disabled while qualifying the restore.
Restore the backup into an isolated non-production target, load the newer erasure
tombstone ledger separately, verify its policy and generation identity, then scan
database rows, pfiles, conversion backups, journals, cache rebuild inputs, and export
spools by stable account-scope hash. Unscoped identities fail closed.

Only a future approved adapter may strip a tombstoned scope, and it must do so before
any restored service is published. Verify that every completed tombstone remains
uncredentialed and unloadable and that all domain reconciliation reports pass. If a
tombstone set is missing, stale, unverifiable, or cannot cover a source class, abandon
that restore candidate; do not reopen it and do not alter historical backups in place.

The backup command selects the explicit persistence mode and applies the
operator-approved shared policy. See [BACKUPS.md](BACKUPS.md) for independent
scheduling, full generations, bounded retention and verified isolated restores.

## 200-player readiness gate

The integrated gate needs a separately configured, backed-up, production-unreachable
representative clone and never reads `.env` implicitly. Its inputs, preflight, procedure
and current state are in [`PHASE03_READINESS.md`](../gates/PHASE03_READINESS.md). Treat a
`QUALIFIED` preflight as permission to begin the isolated gate, not as a readiness result.

## Disabling a DurisWeb hook

During an incident, any single DurisWeb integration can be cut without
restarting the MUD and without affecting the others.

```
properties set durisweb.hook.<id> 0.000
```

Ids: `auction_new`, `auction_bid`, `auction_close`, `player_presence`,
`mud_shutdown`, `wholist`, `admin_delete_character`, `donation_delivery`.
Requires FORGER or above. Re-enable with `1.000`.

The change takes effect immediately and is pushed to connected DurisWeb peers,
which reflect it in their operator console within about ten seconds. It is
in-memory only -- run `properties save` to persist across a restart, or
`properties revert` to undo before saving.

A disabled hook emits nothing at source. `donation_delivery` additionally logs
one `LOG_SYS` line per pulse naming how many events it dropped, so a hook left
disabled is visible in the logs rather than silent.

`connection_log` is not in this list: DurisWeb's connection ingestion is toggled
on the DurisWeb side, because the underlying `logs/log/comm` lines are the MUD's
own operational records.

### Reconciling from the DurisWeb hook console

The website's Hook Control console uses the authenticated
`durisweb_hook_set` command for the eight ids above. This path persists the MUD
property atomically and pushes a complete state frame before acknowledgement;
do not run `properties save` for a successful console change.

Reconciliation is deliberately directional:

1. To disable, the website closes its own gate first and then asks the MUD to
   disable. A bridge failure therefore leaves delivery stopped locally and the
   row shows the partial state.
2. To enable, the website keeps its gate closed, asks the MUD to enable, waits
   for the pushed state, and opens its own gate last. A timeout or refusal
   cannot open delivery.

For a `MISMATCH`, open the row details and confirm which end differs. Use Set
Both Ends only after verifying the intended direction. For `UNKNOWN`, restore
the authenticated bridge first; do not infer that the MUD is enabled. If the
console reports a persistence error, inspect permissions and free space for
`lib/duris.properties` and its `.new` sibling, then retry. Do not hand-edit the
file while the MUD is running.

The five website-only hooks show `MUD: N/A` and reconcile only the website
gate. The terminal is always-on as the recovery path and cannot be reconciled.

## Runtime tuning

Server behavior knobs are exposed through the properties system:
`get_property()` (`src/world/properties.c`) binary-searches key/value pairs loaded
from `lib/duris.properties`, falling back to per-call defaults, e.g.
`help.cooldown.secs`. Feature config files live in `lib/*.cfg`
(crafting, mining, hardcore, frag caps, account rewards, creation
availability, random equipment). Property/config changes take effect on
restart without recompilation; check the owning subsystem docs before
editing.

One property is a live balance switch worth knowing about:
`artifact.wars.modifier` scales the race-war penalty applied by
`event_artifact_wars` -- each of a violating player's artifacts loses
`modifier x punish_level` of its remaining life, clamped to the whole of it.
The code default is `0.0` (forced drop only), but `lib/duris.properties` ships
`artifact.wars.modifier=0.500`, so a server using that file halves the
offender's artifact timers on a first-level violation. Set it to `0` to disable
the timer penalty.

## Development vs production checklist

- Development: local/development/test `ENVIRONMENT`, loopback database host,
  explicit non-production `DB_NAME` in `DB_ALLOWED_TARGETS`, non-7777 listener
  (for example port 4000 via `--dev`), and a `TEST_MUD` build. The port does not
  select the database.
- Production: production `ENVIRONMENT`, an explicit allow-listed database target,
  TLS with an absolute trusted `DB_SSL_CA` whenever database traffic leaves loopback,
  a `BUILD_PROFILE=production` binary, a real listener TLS certificate linked as
  `duris.crt`/`duris.key`, secrets supplied through the protected environment or secret
  store, mode-0700 receipt/state directories, and regularly restored and verified
  backups of MySQL, legacy player/account material, receipts, and erasure tombstones.
  Credentials never belong in source files.

### Release boundary

This repository declares no deployment trigger or service account. Release
authorization and platform rollback are operator-owned decisions made outside it.
Repository-owned validation is the local gate: `./scripts/format.sh --all --check`,
`make test-all`, `make test-db`, and `make security-check`
([TESTING.md](../guides/TESTING.md#before-a-merge)). No hosted pipeline runs.
