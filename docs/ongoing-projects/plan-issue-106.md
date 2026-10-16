# Issue #106: runtime reports and host failures

Tracker: <https://github.com/LuminariMUD/Duris/issues/106>

## Current checkpoint — 2026-10-16

**LR-12 and LR-15 are resolved.** A separately demonstrated limited-zone teleport
caller defect is implemented and tested. Six original gameplay/runtime reports
remain open for missing historical attribution; do not label them fixed by the
new repair or infer their causes from nearby events.

The owner resumed investigation, authorized the scoped host repair and controlled
notification test, then directed reuse of `.env.example`'s MAIL_* fields. The
corrected notifier is installed on the host and the recipient confirmed receipt
of the real OnFailure test. No game restart, database write, merge, or release tag
was performed.

Worktree: `/home/aiwithapex/projects/duris-issue106`.
Current branch: `branch/issue-106-backup-alert-mail`.
The primary checkout belongs to other work and must remain untouched.

Review-ready stack:

1. [#117](https://github.com/LuminariMUD/Duris/pull/117),
   `branch/issue-106-runtime-evidence`: recovered logs and initial continuation.
2. [#120](https://github.com/LuminariMUD/Duris/pull/120),
   `branch/issue-106-limited-teleport`: actual Teleport/Depart/Etheric Gust repair.
   Tested implementation commit: `60f6911b4`; subsequent changes are documentation.
3. [#124](https://github.com/LuminariMUD/Duris/pull/124),
   `branch/issue-106-host-diagnosis`: protected host diagnosis and operational proof.
4. [#126](https://github.com/LuminariMUD/Duris/pull/126),
   `branch/issue-106-backup-alert-mail`: maintained notifier, MAIL_* contract,
   focused executable regression, and final host qualification.

## Outcome, scope, and ablation

- Outcome: evidence-backed dispositions for LR-06/07/09/10/12/15/17/18, repairs of
  demonstrated defects, adequate continuation records, and focused review-ready PRs.
- Non-goals: #82's release/replica/restore/monitor work, #57's separate PSP and
  over-cap movement defects, speculative balance changes, merging or game rollout.
- Files: the narrow spell callers and existing graph regression; maintained
  backup notifier/test, existing mail configuration example and backup guide;
  this plan and the historical review reference.
- Proof: actual retained records and production source, native executable
  regressions, required server build, host rotation/ownership/write observations,
  and real OnFailure delivery/receipt/suppression. Local adapters cannot replace
  host acceptance.

Reuse merged #74/#75 repairs and the existing environment loader. No cache,
monitoring service, alternate alert system, duplicate password file, speculative
optimization, or general test framework was added. The initially considered
curl/credential-file candidate was replaced by the smaller existing MAIL_*/Python
SMTP path. The temporary Plesk exception was removed after the notifier no longer
needed the shared relay.

## Six original reports: current evidence and exact gaps

- **LR-06 — zone/catalog attribution:** original `chat:56` contains the displayed
  `-2`, not the room/zone. `status:797` records successful boot catalog creation
  (351 zones, 17,175 mobile profiles). Current bootstrap populates normal averages,
  assigns `-1` to empty normal zones, and can retain `-2` for special zones. This
  is a boot-cached prototype catalog, not a live population counter. #74's sentinel
  display/bounds repair remains verified. Need the original room/zone before
  attributing its population or refresh behavior; nearby resets/teleports do not
  establish the reporter's location.
- **LR-07 — movement conditions:** `chat:100` has no timed resource measurements.
  Need race/class/level, posture/status, terrain, carried load, movement mode and
  effects, recovery settings, current/max resources, actions, pulses/wall time,
  and combat transitions. No balance change is established. #57 remains separate
  until a matching reproduction connects it to this report.
- **LR-09 — dead-owner producer:** `debug:2317` confirms the rejected schedule at
  02:22:26 UTC but no combat/effect caller; the NPC was already outside the world.
  #75's demonstrated damage/cleave continuation fix passes its executable test.
  Need the original effect/combat sequence; retain scheduler rejection, extraction
  cleanup, and owner-reuse protection.
- **LR-10 — posture producer:** `debug:2476` confirms recovery at 04:32:03 UTC,
  without the prior HP/posture/action sequence. #75's demonstrated healing repair
  passes; that does not prove this timestamp's cause. Need the producing action
  or a matching reproduction, preserving valid posture/status combinations.
- **LR-17 — lookup/query/load:** exact live boot/tick correlation is recovered:
  boot `1791841938562830-4152756`, tick `76404`, lookup **73.738 ms**, command sweep
  **73.847 ms**, whole tick **80.744 ms**. The sweep observed one playing command
  and eight descriptor operations totaling 84 microseconds, not a verified player
  count. The window's maximum event section was 15.820 ms at another tick, 76485.
  Four one-tick deferral reports occurred elsewhere (23:09:54, 04:40:17, 04:42:47,
  05:12:50 UTC). No 250 ms overrun or justified optimization is established.
  Original mode/query and player load remain unavailable.
- **LR-18 — original pathfinding caller:** all 22 room-budget and 15 distance-limit
  diagnostics retain runtime source/target room indices, but no caller or maximum
  distance. They are not stable virtual room numbers. Several bidirectional pairs
  fit multiple consumers and cannot uniquely identify the producer. #75's distance
  boundary fix and the new caller repair are demonstrated separately; neither
  proves the causes of those original exits.

The original rotation is `/home/staging/duris/logs/old-logs/2026.10.13-21.10.17`.
A private copy is under `bin/analysis/issue106/private/original/`. Its `cmd.debug`
contains only the final 500 commands, at 20:51:17–21:10:06 UTC on October 13;
`src/core/debug.c` keeps that bounded in-memory ring and flushes it at exit.
The earlier sequences are absent. Staff, level, death and other player logs were
also inspected and do not provide the complete sequences.

A read-only database transaction with a five-second statement limit checked
`log_entries` around all five report timestamps and `telemetry_interval` over
the entire original seven-hour window. Only nearby unrelated staff/player actions
were found; telemetry had no records in the window. Their room metadata cannot
be assigned to these reports. Private queries/results and reader are retained
under `bin/analysis/issue106/`; no credentials or player identities are committed.

## Demonstrated teleport repair

Teleport, Depart, and Etheric Gust previously returned unconditionally inside
virtual rooms 5700–5999 even when `how_close()` found an adjacent valid destination.
They now reject only a negative result, preserving the five-room restriction,
destination selection, eligibility checks and failure feedback.

The extended `test_graph_distance_runtime.py` executes all three actual spell
bodies with the real graph, structs, edge macros and queue under ASan/UBSan.
Self/distinct targets, same/adjacent/exact-five/over-range/unreachable destinations,
ordinary zones, combat cleanup/preservation, wait and queue reuse pass. Restoring
each original caller separately fails with the adjacent destination remaining in
room zero. RNG, permissions, presentation/movement endpoints and wait are adapters;
no live player cast, persistence journey, or historical attribution is claimed.

## LR-12 resolved: duplicate rotation rule and subsequent recovery

The protected journal names `cloud-init-base:1` as a duplicate entry for
`/var/log/cloud-init-output.log` on October 13 and 14. The Plesk hook was not the
failure. The current rule set contains one `/var/log/cloud-init*.log` rule.
`sudo logrotate --debug /etc/logrotate.conf` exits zero without changing logs/state.
Three subsequent service runs succeeded, including October 16 00:06:02–00:06:07 UTC.

Cloud-init's policy is `su root root`, `nocreate`, `notifempty`, six rotations,
compression/delaycompress and a 1 MiB size threshold. Its files are inactive since
October 9 and below threshold (78,599/288,941 bytes), with owners/modes
`root:adm`/0640 and `syslog:adm`/0640. They did not need forced rotation.

The same service's Apache rule uses `create 640 root adm`; current and rotated
origin-access logs match. A harmless GET of a nonexistent ACME challenge returned
404 and produced the expected log entry. The active file grew 65,569 → 65,710
bytes at 08:55:48 UTC, retaining inode 335254 and correct permissions; rotated
inode 273033 stayed unchanged. This proves continued writes after successful
rotation. No rotation configuration was changed by this investigation; the prior
duplicate's removal actor/time is not inferred.

## LR-15 resolved: verified SMTP and real recipient receipt

Protected October 12/15 journals show Plesk rejecting standalone UID 10014 before
queuing mail. It had neither a registered subscription nor a system-user exception.
With explicit owner approval, staging was added temporarily to that exception list.
The first harmless OnFailure test then submitted successfully, but the shared
SMTP2GO relay permanently rejected the default unverified From domain. Postfix
recorded a bounce and removed the queue entry; no recipient message was delivered.
A repeat was suppressed and that test unit/stamp were removed.

The owner's supplied SMTP2GO account has a verified single sender; the shared
Postfix relay uses a different account. The final fix changes only the existing
backup notifier, leaving the shared relay unchanged:

- Production `.env` now has MAIL_HOST/PORT/TLS/USERNAME/PASSWORD/FROM populated
  from the supplied account and verified sender. Mode 0600, MAIL_ENABLED, and
  unrelated values are preserved. The owner's extra SMTP2GO values retain safe
  shell quoting. No second password file was created.
- `scripts/backup_alert.py` is installed at the existing staging
  `~/.local/libexec/duris-backup-alert` path, mode 0700. Its existing user-unit
  template now supplies `--recipient` and `--env-file`. Unit verification and
  user-manager daemon-reload passed; no game service was restarted.
- The notifier reuses the protected literal `.env` loader and standard Python
  SMTP with verified STARTTLS, a 30-second socket timeout and a bounded 20-line
  user-journal read. Accepted submission stamps before QUIT; failed submission
  remains eligible. The existing one-hour per-unit window is preserved.
- The task-created Plesk staging exception was removed. The final exception list
  matches the original five entries. No global mail controls were disabled.

At **09:26:25 UTC**, transient user unit
`duris-backup-alert-test-20261016-verified.service` deliberately ran `/usr/bin/false`.
Its real OnFailure route invoked the installed notifier, which exited zero at
09:26:27. SMTP2GO reports **Delivered at 09:26:31 UTC**, including Google's
`250 2.0.0 OK` response. The owner independently confirmed receipt and pasted the
matching test message in this chat. This establishes recipient receipt, not only
SMTP acceptance.

The same harmless failure repeated at **09:27:52 UTC**; notifier exit was zero,
the stamp stayed at epoch 1792142787, and SMTP2GO still showed **one total email**.
The test unit was reset/unloaded and its test-only stamp removed; final state is
not-found/inactive. Original backup and health services retain their OnFailure
routes. There is no installed drill service/timer; #82's deferred drill enablement
was not started.

Installed source SHA-256 equals repository `scripts/backup_alert.py`:
`a7fc1007bb31c6d071e28314085245f04e7d939e1e51a69bed932a2fbeef2d73`.
Private rollback copies of the former notifier/unit remain in staging's
`~/.cache/duris-issue106/`. Restoring that old notifier alone would restore the
known delivery failure; do not do so without a separate mail-path correction.

PR #126 review exposed five additional gaps, all repaired: port 465 now uses
verified implicit TLS; optional SMTP credentials are accepted only as a pair;
journal failure/timeout produces an explicit placeholder instead of suppressing
the notification; the account-recovery comment contract matches the shared
settings wording. Unauthenticated loopback plaintext also retains the documented
shared-mail exception. Remote plaintext and partial credentials remain rejected.
The production deployment runbook now describes the verified direct-SMTP notifier
and removes its obsolete recommendation to add a Plesk account exception.
The expanded six-test notifier suite fails against the original implementation
(one failure, six subtest errors) and passes after these repairs. The existing
account-recovery source contract also fails before and passes after. The reviewed
script is installed and hash-matched. The successful live 587/authenticated path
is unchanged; the added variants have local executable proof, with no extra test
email sent.

## Verification and retained evidence

Passed:

- `make -C src -j4` for the unchanged C/C++ repair (development/MariaDB server).
- `python3 tests/async/test_graph_distance_runtime.py` plus three individual
  original-caller negative controls.
- Focused `test_zone_average_display.py`, `test_world_quest_dynamic_policy.py`,
  `test_move_cost_runtime.py`, `test_damage_death_result.py`,
  `test_posture_state_regression.py`, `test_nevent_scheduler_runtime.py`,
  `test_nevent_cancellation_runtime.py`, and `test_command_latency_runtime.py`.
- `python3 tests/async/test_backup_alert_runtime.py` (six tests): actual .env
  loader, verified STARTTLS/implicit TLS, optional paired auth, loopback-only
  plaintext, From/envelope/recipient, false MAIL_ENABLED, rejected submission/
  retry, per-unit suppression, expiry, unavailable journal, and unsafe-file
  rejection. SMTP/journal are adapters.
- `python3 tests/async/test_account_recovery_contract.py`.
- `python3 tests/async/test_documentation_contract.py` (14 checks), formatting,
  applicable commit hooks, and `git diff --check`.
- Actual host checks and receipt described above; real repeat suppression/cleanup.

All raw logs, identities, mail addresses, provider IDs, credentials and generated
artifacts stay outside Git. Evidence is in ignored `bin/analysis/issue106/`:
original logs, `private/host-journals/*.jsonl`, `host-config.json`, `log-write-*.txt`,
first failed delivery records, `verified-alert-first.txt`,
`verified-alert-repeat.txt`, `verified-alert-cleanup.txt`, and the before/final
Plesk lists. Protected access is through the owner-designated WSL `ssh lumi`.

## Resume here

1. Review the published stack; completed repairs need no new feature work. The
   installed notifier is explicitly authorized operational work and does not
   authorize merging or deploying the game changes.
2. Keep #106 open for LR-06/07/09/10/17/18. Their next useful input is a retained
   contemporaneous transcript/state snapshot or original reporter's repeatable
   sequence with the conditions listed above. Current player files or nearby
   events are not proof. Do not manufacture code changes or claim exact attribution
   from representative tests.
3. If new evidence establishes another defect, reproduce it with the closest
   existing test and publish a separate focused repair. Keep #57/#82 ownership
   boundaries and all private evidence constraints.
