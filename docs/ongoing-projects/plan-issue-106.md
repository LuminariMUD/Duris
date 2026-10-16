# Issue #106: runtime reports and host failures

Tracker: <https://github.com/LuminariMUD/Duris/issues/106>

## Current checkpoint — 2026-10-16

The owner explicitly resumed this issue and requested autonomous investigation,
repairs, focused review-ready PRs, and this continuation record. The 2026-10-14
deferral in [the historical review](log-server-review.md) is superseded for
investigation of these eight items. The owner subsequently approved the scoped
Plesk exception and one-email acceptance test. That test exposed the relay
sender/account mismatch described below; the next notifier-only transport
correction is prepared for specific approval. Historical causes are not assumed.

Worktree: `/home/aiwithapex/projects/duris-issue106`.
Evidence branch: `branch/issue-106-runtime-evidence`, starting at master `b149b3ada`,
published as [PR #117](https://github.com/LuminariMUD/Duris/pull/117), commit `ea9af99a4`.
Repair branch: `branch/issue-106-limited-teleport`, published as
[PR #120](https://github.com/LuminariMUD/Duris/pull/120), stacked on #117.
The tested implementation commit is `60f6911b4`; later checkpoint edits are docs only.
Current host-diagnosis branch: `branch/issue-106-host-diagnosis`, published as
[PR #124](https://github.com/LuminariMUD/Duris/pull/124), stacked on #120.
Current implementation branch: `branch/issue-106-backup-alert-mail`, stacked on
#124; it adds the maintained notifier and shared MAIL_* configuration contract.
The primary checkout belongs to other work and must remain untouched.

## Outcome, non-goals, files, and proof

- Outcome: establish an evidence-backed disposition for LR-06, LR-07, LR-09,
  LR-10, LR-12, LR-15, LR-17 and LR-18; repair demonstrated defects and publish
  each qualified chunk for review. Preserve missing evidence explicitly.
- Non-goals: #82 release/restore/replica/monitor work; #57 PSP and over-cap
  movement fixes; balance changes from an unverified comment; deployment,
  merging, historical data replacement, and release tags.
- Files: this plan and the existing review reference first; only the source,
  existing focused tests, and operational documentation justified by findings.
- Proof: original retained records plus traced current code and actual deployed
  definitions; relevant executable tests and `make -C src` for C/C++ changes;
  observed rotation/ownership/live writes for LR-12 and recipient receipt plus
  delivery/retry/rate-limit checks for LR-15. Local tests cannot replace those
  host acceptance conditions.

## Ablation decision

Reuse the merged #74/#75 repairs, existing diagnostics, and native/runtime tests.
Do not add a cache, monitoring service, alternative notifier, general test rig,
or speculative gameplay fix. Historical causality requires contemporaneous
evidence; reproducing a possible cause alone does not establish it.

## Active investigation

1. Recover retained October 13 logs and deployed rotation/alert definitions
   through the existing host account, using read-only commands. Keep raw logs,
   mail addresses, and player data private and outside Git.
2. Correlate original room/zone, movement conditions, combat/posture producers,
   lookup query/load, and pathfinding caller/rooms where records permit.
3. Reproduce any demonstrated current defect with the closest existing test,
   repair it, verify it, and open a focused PR immediately when ready.
4. Record each item's disposition and exact remaining evidence. Obtain any
   necessary production/test-notification authorization only after a concrete
   correction or test is prepared for review.

## Per-item evidence and next action

- LR-06: display repair is merged (#74). Original room/zone is still unverified;
  inspect retained chat/player context and the catalog population/refresh path.
- LR-07: no balance defect is established by the comment. Recover contemporaneous
  conditions before correlating with #57 or changing movement/recovery.
- LR-09: #75 repairs demonstrated damage/cleave continuation after simultaneous
  death. Recover the producer of the 02:22:26 guard report; retain dead-owner,
  extraction and owner-reuse protections.
- LR-10: #75 repairs demonstrated healing into standing/resting. Recover the
  04:32:03 producing transition; preserve legitimate posture/status combinations.
- LR-12: resolved by recovered duplicate cloud-init rule diagnosis, current
  configuration validation, successful scheduled rotation, matching ownership,
  and observed continued live writes; see the protected diagnosis below.
- LR-15: Plesk's standalone-user rejection is repaired with owner approval.
  The real OnFailure test exposed a relay rejection of the default sender
  domain; recipient delivery remains open pending a verified sender address.
- LR-17: representative lookup profiling already found no justified optimization.
  Recover exact mode/query/load and correlate command/loop/callback evidence.
- LR-18: #75 fixes acceptance beyond maximum distance. Recover historical
  source/target/caller and retain room/distance bounds and queue cleanup.

## Recovered evidence — 2026-10-16

Read-only SSH through `duris-staging` recovered the original log rotation at
`/home/staging/duris/logs/old-logs/2026.10.13-21.10.17`. A private local copy is
under `bin/analysis/issue106/private/original/`; the original archive, service
inventory, and host diagnostics are beside it. These ignored files contain
player identities and mail addresses and must not be committed or posted.

- **LR-06:** the original chat line 56 is retained, but contains only the
  displayed value, not the reporting room/zone. The preceding boot's `status:797`
  records a successful world-quest catalog: 351 zones and 17,175 mobile profiles.
  Current `world_quest_policy_bootstrap()` populates normal-zone averages and
  assigns `-1` to normal zones without profiles; special zones can retain `-2`.
  It is a boot-cached catalog, not a periodic/live-population count. The display
  reads the current field on each command. Neither a nearby reset nor a later
  staff teleport proves the reporting location. Exact attribution stays open.
- **LR-07:** chat line 100 gives an impression, without resource measurements,
  timed actions, terrain, load, effects, or combat transitions. Nearby staff
  modifications concern multiple characters and cannot supply that missing
  state. #57 remains the owner of its separately reproduced defects. No new
  movement or balance change is supported.
- **LR-09:** `debug:2317` confirms the rejected schedule at the original time,
  but records no combat/effect caller. The owner was already outside the world.
  Surrounding records do not establish the producing action sequence.
- **LR-10:** `debug:2476` confirms the recovery at the original time but does
  not record the prior HP/posture/action sequence. Nearby events cannot prove
  that the demonstrated #75 healing transition caused this occurrence.
- **LR-17:** `status:3754–3757` and `latency_trace.log:7624–7649` share boot
  `1791841938562830-4152756`, tick `76404`. The actual lookup took **73.738 ms**;
  the command sweep took **73.847 ms**, and that exact whole tick took
  **80.744 ms**. The sweep observed one playing command and eight descriptor
  operations (84 microseconds total); this is not an authenticated player count.
  The same 300-tick window's maximum event section was **15.820 ms at tick
  76485**, not at the lookup tick. All four one-tick event deferral windows
  occurred elsewhere: 23:09:54, 04:40:17, 04:42:47 and 05:12:50 UTC. Thus the
  retained live evidence does not connect these deferrals to this lookup or
  show a 250 ms pulse overrun. Exact query/mode and player load remain unknown;
  no optimization is justified by this evidence.
- **LR-18:** the original 22 room-budget and 15 distance-limit diagnostics do
  retain source/target **runtime room indices**, contrary to an interpretation
  that all room evidence was absent. They omit the caller and maximum distance.
  Several bidirectional pairs match the shape of multiple teleport consumers,
  so their exact producer cannot be uniquely inferred. Do not treat these as
  stable virtual room numbers or reconstruct them from today's world layout.

The archived `cmd.debug` contains only the final 500 commands from 20:51:17 to
21:10:06 UTC on October 13. `src/core/debug.c` implements that bounded ring and
flushes it at exit. It cannot recover the earlier sequences above. The archived
staff command, level, death, and other player logs were also inspected; none
supplies the missing complete sequences. Preserve this limit instead of adding
unbounded command capture or claiming retrospective causality.

### Database attribution cross-check — 2026-10-16

The continuation also queried the deployed database through its existing
allowlisted connection, using a read-only transaction and a five-second
statement limit. Bounded `log_entries` reads around 02:50:05, 03:16:50, 02:22:26,
04:32:03, and 03:11:02 UTC produced nearby staff actions and one unrelated player
action, but no matching zone report, movement report, dead-owner producer,
posture producer, or lookup query. Their room metadata belongs to those other
actions and must not be assigned to the reports. The `telemetry_interval` query
for the full original seven-hour window returned no records, so its potential
zone/race/class/encounter fields supply no retrospective evidence here.

Private query inputs and outputs are under `bin/analysis/issue106/private/`
(`historical-audit.tsv` and `telemetry-attribution.sql/.tsv`); the read-only reader
is `bin/analysis/issue106/read_historical_audit.py`. Connection values and player
identities were not added to the repository. No database writes were performed.

### Host access and notifier baseline

Protected diagnosis now uses the owner-designated WSL `ssh lumi` account with
sudo. Authentication is resolved; the earlier blocked attempts are superseded.
No credentials are stored in the repository or private evidence. The completed
collection helper and five original JSONL files remain in the owner's private
`~/.cache/duris-issue106/` directory and the local ignored analysis directory.

The actual deployed notifier is `~/.local/libexec/duris-backup-alert` under the
staging account. Both installed source units (`duris-backup-backup` and
`duris-backup-health`) route through `OnFailure=duris-backup-alert@%N.service`.
Its shell uses `set -euo pipefail` and stamps a per-unit one-hour quiet period
only after successful sendmail submission. Historical exit-100 attempts left
no stamps; this protected-mail cause and current live test are detailed below.

The captured notifier was executed locally with synthetic state, journal, and
sendmail adapters. Exit 100 leaves no stamp; successful retry creates one;
immediate repeat is suppressed; an expired failed attempt does not refresh the
stamp; a subsequent successful retry does. This qualifies submission/stamp
control flow, not recipient receipt. The executable probe is
`bin/analysis/issue106/check_installed_alert.py`.

## Demonstrated additional caller defect — implemented and qualified

Tracing LR-18 consumers found `spell_teleport`, `spell_depart`, and
`spell_etheric_gust` unconditionally return inside `LIMITED_TELEPORT_ZONE` even
when `how_close()` reports a reachable destination within five rooms. Their
truthiness check also treats a valid positive distance as failure. The zone
restriction is virtual rooms 5700–5999. This is independent of attribution of
the original 37 diagnostics.

The fix rejects only a negative `how_close()` result in those three callers.
It adds no helper or option and preserves the existing five-room cap, destination
selection, eligibility checks, and failure text. The existing graph regression
now invokes all three actual spell bodies with real structs, edge macros,
queue, and pathfinder. It covers self and distinct-target casts, same-room,
adjacent, exact-five, six-room, far/unreachable destinations, unchanged ordinary
zone travel, unchanged combat on rejection, success combat cleanup, wait timing,
and empty-queue reuse. RNG, permission, presentation, movement endpoints and wait
are controlled adapters; this is not a live player/server cast or persistence
journey. Dispatch remains through the existing registered spell functions.

Individually restoring each original caller makes the extended executable fail
with `limited teleport target=1 stayed in room 0`; all three fixed callers pass
under ASan/UBSan. The retained before/after and per-caller negative controls are
under `bin/analysis/issue106/`. The unused commented-out teleport block elsewhere
in `magic.c` is not a compiled caller and was left alone.

## Verification and publication

Passed:

- `make -C src -j4` (development/MariaDB server, `bin/server/dms_new`).
- `python3 tests/async/test_graph_distance_runtime.py` (real graph plus three
  spell bodies, ASan/UBSan; three separate original-caller failures confirmed).
- `python3 tests/async/test_zone_average_display.py`
- `python3 tests/async/test_world_quest_dynamic_policy.py`
- `python3 tests/async/test_move_cost_runtime.py`
- `python3 tests/async/test_damage_death_result.py`
- `python3 tests/async/test_posture_state_regression.py`
- `python3 tests/async/test_nevent_scheduler_runtime.py`
- `python3 tests/async/test_nevent_cancellation_runtime.py`
- `python3 tests/async/test_command_latency_runtime.py`
- `python3 tests/async/test_documentation_contract.py` (14 checks).
- `./scripts/format.sh --check` and `git diff --check`.

The owner-approved Plesk exception for staging is applied. The harmless
transient failure test and its stamp were cleaned up. Game services and player
files are unchanged. The read-only HTTP probe produced an access-log entry.
No merge or release tag is appropriate for these unreviewed PRs.
Do not close #106 while its missing historical/operational acceptance remains.

## Resume here

Review #117 and the stacked caller-fix PR. The completed repository repair needs
no additional feature work. For the remaining original items:

1. Authentication is now resolved and the five protected journals are collected.
   The owner approved and the agent applied the staging mail exception. The
   failed delivery was traced to the shared relay's different account. The
   owner supplied an account whose single sender is visibly verified. The
   owner authorized the fix and requested use of `.env.example`'s existing
   MAIL_* names. The maintained notifier below now reuses those values from
   the existing production `.env`; installation and live delivery are next.
2. After an authorized repair/test, record the rotation target's ownership and
   continued writes, actual `OnFailure=` delivery/receipt, source-unit coverage,
   retry eligibility, and bounded repeats. Local adapter results cannot close
   those conditions.
3. Exact LR-06/LR-07/LR-09/LR-10/LR-17/LR-18 historical attribution needs an
   independently retained contemporaneous transcript/snapshot or the original
   reporter's repeatable sequence. The inspected text logs and database audit
   records do not contain it. Current
   player files, nearby staff changes, or the new teleport repair are not proof
   of those historical causes. Keep each evidence gap explicit in #106.

## Protected diagnosis recovered — 2026-10-16

The owner supplied the remote-server credential, authentication succeeded, and
the prepared read-only collection completed. The five original JSONL journals
are now under `bin/analysis/issue106/private/host-journals/`; credentials are not
stored in the checkout or evidence files. This supersedes the earlier access
blocker. `host-config.json`, the installed Plesk CLI help, and selected local
log metadata retain the subsequent read-only investigation.

### LR-12: resolved — duplicate cloud-init rule; correction already present

The October 13 journal identifies `cloud-init-base:1` as a duplicate entry for
`/var/log/cloud-init-output.log`; it is not a failure of the Plesk hook. The same
duplicate recurred on October 14. Three subsequent executions completed
successfully, including the scheduled October 16 00:06:02–00:06:07 UTC run.

Current `/etc/logrotate.d/cloud-init-base` is the sole loaded match for
`/var/log/cloud-init*.log`. Its policy is `su root root`, `nocreate`, `notifempty`,
six rotations, compression/delayed compression, and a 1 MiB size threshold.
`sudo logrotate --debug /etc/logrotate.conf` exits zero without duplicate-rule
errors or state/log changes. Both cloud-init files are below that threshold
(78,599 and 288,941 bytes), and have no activity since October 9; their absence
of a fresh rotation is expected. Their owners/modes are `root:adm`/0640 and
`syslog:adm`/0640; `nocreate` preserves them. No forced rotation or artificial
write to these inactive boot logs is warranted.

The same service's Apache rule uses `create 640 root adm`; the retained origin
access `.log.1` and current `.log` have those owners/modes and different inodes.
The current file's mtime is after the successful scheduled rotation. A harmless
HTTP GET to a nonexistent ACME challenge path on the configured local origin
vhost returned 404 and produced the expected access-log entry. The active file
grew from 65,569 to 65,710 bytes at 08:55:48 UTC while retaining inode 335254 and
`root:adm`/0640; rotated inode 273033 remained unchanged. This confirms the
writer still uses the current file after rotation. No host
configuration was changed by this investigation; the prior duplicate's removal
actor/time is not inferred from the currently correct file set.

LR-12's root cause, corrected rule set, successful scheduled service run, owner/
mode checks, and continued live-write acceptance are now established. The
cloud-init files themselves are inactive below-threshold boot logs; no claim is
made that they required or received another rotation. Raw metadata and the
matching probe entry are retained privately as `log-write-*.txt`.

### LR-15: standalone system account rejected by Plesk policy

The protected October 12 and October 15 journals consistently show Plesk's
`py-limit-out` rejecting UID 10014 (`staging`) with SMTP 554/5.7.0 before queuing
the alert. The deployed handler's actual rejection branch requires either a
registered subscription system user or an explicit system-user exception.
Read-only Plesk database queries find no subscription/sysuser entry for
`staging`; `mailmng-outgoing --show-whitelist` also omits it. This establishes the
cause of exit 100. Changing the sender header, resetting a failed flag, or
rewriting the already-working success-only stamp logic would not fix it.

The installed `plesk sbin mailmng-outgoing --help` provides the scoped command:

```bash
sudo plesk sbin mailmng-outgoing --add-to-whitelist --sysuser=staging
```

Rollback is the same command with `--remove-from-whitelist`. The exception
allows **all processes running as staging** to use sendmail without Plesk's
outgoing limits; it is not restricted to the backup notifier. The existing
notifier still enforces one successful alert per unit per hour. Do not disable
global mail controls or add a second notifier. The owner explicitly approved
the exception and one-email test; the exception was applied and read back.
The list changed only by adding `staging`.

### Prepared operational acceptance

After approval of the per-user mail exception and external test notification:

1. Capture the existing exception list and recheck the notifier/source units.
   Apply the single-user exception and read it back. Preserve global policy.
2. Use a uniquely named transient **user** unit whose harmless command is
   `/usr/bin/false` and whose `OnFailure` targets the installed
   `duris-backup-alert@.service`. Do not fail a real backup or health check.
3. Verify a queued message and delivery through the actual mail path to the
   existing configured backup recipient. Require recipient receipt, not only
   successful sendmail submission. Keep addresses/mail content private.
4. Repeat the same harmless unit failure once; verify the notifier's same-unit
   quiet-period stamp suppresses a second message. Local adapter tests already
   prove failed submission/no-stamp, retry, expiration, and success-only stamps.
5. Record all actual source-unit routes, including how any enabled drill is
   invoked. Do not enable #82's deferred drill/replica work. Clean up only this
   test's transient unit/stamp after preserving its evidence.

AGENTS.md's production rule and #106's explicit controlled-notification
requirement are the reasons approval is required for these two actions.

### Live OnFailure test: submission fixed, relay sender rejected

At 08:58:55 UTC, transient user unit `duris-backup-alert-test-20261016.service`
ran `/usr/bin/false` and failed as intended. Its explicit `OnFailure` dependency
invoked the existing notifier template. The alert service returned zero and
created its success-only quiet-period stamp. Plesk accepted UID 10014 and the
message entered Postfix as queue `8BE6B81CF4`.

The configured SMTP2GO relay then permanently rejected the message: the From
header's `plesk.luminarimud.com` domain is not verified. Postfix recorded
`status=bounced` and removed the queue entry. **No test message reached the
recipient.** Current Postfix uses its hostname as origin and has no generic or
sender-canonical rewrite. A bounded October 12–16 journal check found no prior
successful SMTP2GO delivery establishing a usable sender domain. The required
next correction is an explicit approved, verified From/envelope sender in the
existing notifier; do not alter the global relay or register a guessed sender.

Repeating the same harmless failure at 08:59:33 UTC invoked the notifier a second
time, but produced no second sendmail attempt. The stamp remained at epoch
1792141136. This proves live repeat suppression through OnFailure, while the
local adapters prove failed-submission retry/expiry. It also demonstrates why
submission success alone cannot establish recipient receipt. No second test
email was submitted. The transient unit was reset/unloaded and its test-only
stamp removed after evidence capture; final state is not-found/inactive.

Route inventory has only backup and health services and their two enabled
timers, plus the alert template. Both actual sources have the correct route.
There is no installed drill service/timer; #82's deferred drill enablement is
not part of this repair. The local backup schedule performs backups/status,
not an implicitly enabled restore drill.

Evidence: `private/alert-live-first.txt`, `alert-live-repeat.txt`,
`alert-delivery.jsonl`, `alert-test-cleanup.txt`, and before/after Plesk lists.
Addresses and message content remain private. The relay also logged a
`check-quota` missing-map warning, then `SKIP`; the explicit SMTP2GO sender
rejection is the delivery failure established for this message.

### Verified account and prepared notifier-only transport

Using the account supplied by the owner, the SMTP2GO UI's **Single sender
emails** tab shows the account address as **Verified**, and **SMTP Users** lists
the supplied SMTP username. The existing server-wide Postfix relay uses a
different SMTP account, confirmed by reading only its configured username.
Changing the global relay would affect unrelated services and is not proposed.
Account names, addresses, and credentials are kept out of this public plan.

The smallest isolated correction keeps the existing notifier, source-unit
routes, body, recipient, and per-unit success-only stamp. Its mail pipeline uses
the already-installed `/usr/bin/curl` with required STARTTLS and certificate
verification against `mail-eu.smtp2go.com:587`, the verified From/envelope
sender, a 10-second connection timeout, and a 30-second total timeout. Only the
supplied SMTP login is read from a staging-owned
`~/.config/duris-backup-alert/smtp.conf` (directory 0700, file 0600); the browser
account password is not needed on the host. Credentials will not be committed
or passed as process arguments. No new service or mail framework is added.

Private reviewable candidate:
`bin/analysis/issue106/private/duris-backup-alert.candidate`.
`bash -n` passes. The existing notifier probe passes with a local transport
adapter: failed submission leaves no stamp, retry succeeds, duplicate is
suppressed, an expired failure remains eligible, and later success stamps.
The host's installed curl explicitly supports SMTP/SMTPS and TLS. No runtime
SMTP credential file or candidate installation has been made yet.

Proposed installation: retain a private copy of the current notifier, install
the protected SMTP configuration and checked script under the staging account,
remove this task's now-unneeded Plesk staging exception, then retry a single
harmless transient-unit OnFailure test. The original test permanently bounced,
so no recipient message has been delivered. Verify actual SMTP2GO delivery and
recipient receipt, repeat suppression, and test-only cleanup. Restore the
original notifier and remove only the new credential file if rollback is needed.

### Accepted simplification: existing MAIL_* fields, no second secret file

The owner authorized fixing the notifier and clarified that the SMTP credentials
were already in production `.env`. Use the documented MAIL_* fields instead of
introducing another credential file or making the SMTP2GO dashboard login part
of the runtime. The earlier curl/config-file candidate is superseded.

`scripts/backup_alert.py` is the maintained replacement for the existing
notifier executable. It reuses `persistence_backup.load_environment()` and
Python's standard SMTP/TLS library. This removes the need to translate secrets
into a curl config or command argument. It preserves the recipient, unit journal
body, per-unit one-hour stamp, retry after rejected submission, and OnFailure
routes. An accepted submission stamps before QUIT so a later disconnect cannot
cause duplicate mail. `MAIL_ENABLED` remains exclusively the game's
account-recovery switch. TLS certificate/hostname validation is required.

Install a copy as the existing staging executable and update its existing user
unit's ExecStart with `--recipient` and `--env-file`; no new service is added.
Populate MAIL_HOST/PORT/TLS/USERNAME/PASSWORD/FROM from the supplied SMTP values
and the verified sender in `.env`. Preserve MAIL_ENABLED and unrelated values;
retain mode 0600 and safe shell quoting for the owner's extra SMTP2GO fields.
No password is copied into Git or a second runtime config.

`python3 tests/async/test_backup_alert_runtime.py` passes with the actual
protected environment loader, verified TLS context, From/envelope/recipient
checks, false MAIL_ENABLED, failed submission and retry, per-unit suppression,
expired failures, and rejection of an unsafe environment file. SMTP transport
and journal reads are adapters; actual recipient delivery remains due.
`python3 tests/async/test_documentation_contract.py` passes 14 checks.
