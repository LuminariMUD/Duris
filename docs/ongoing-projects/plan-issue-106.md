# Issue #106: runtime reports and host failures

Tracker: <https://github.com/LuminariMUD/Duris/issues/106>

## Current checkpoint — 2026-10-16

The owner explicitly resumed this issue and requested autonomous investigation,
repairs, focused review-ready PRs, and this continuation record. The 2026-10-14
deferral in [the historical review](log-server-review.md) is superseded for
investigation of these eight items. It does not authorize production changes or
external test notifications. No new defect or historical attribution is assumed.

Worktree: `/home/aiwithapex/projects/duris-issue106`.
Branch: `branch/issue-106-runtime-evidence`, starting at master `b149b3ada`.
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
- LR-12: historical logrotate exit 1 with a Plesk drop-in. Read current unit
  state and available journal; identify the failing rule/hook before any repair.
- LR-15: historical alert exit 100; actual installed notifier differs from
  checkout templates. Inspect that implementation and mail failure evidence;
  no controlled external notification has been authorized or sent.
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

### Host evidence and access boundary

- **LR-12:** `systemctl show logrotate.service` now records `Result=success`,
  `ExecMainStatus=0`, start **2026-10-16 00:06:02 UTC**, exit **00:06:07 UTC**.
  The Plesk drop-in is still installed. This is a real subsequent service
  success, but does not identify the October 13 failing rule/hook. The account
  cannot read the system journal, Plesk log directory, or logrotate state file.
  `/var/log/syslog` metadata shows mode 0640, owner `syslog:adm`, and continued
  writes, but does not prove the unidentified failed target's ownership/writes.
  Keep root cause and target-specific acceptance open.
- **LR-15:** inspected the actual `~/.local/libexec/duris-backup-alert` and
  user-unit template. Both real instances (`duris-backup-backup` and
  `duris-backup-health`) still failed with exit **100**, most recently at
  **2026-10-15 16:37:17** and **16:32:35 UTC**, respectively. Both source units
  have `OnFailure=duris-backup-alert@%N.service`. The installed script invokes
  `/usr/sbin/sendmail -t`, inherits the service-account envelope sender, uses
  `set -euo pipefail`, and touches its per-unit one-hour stamp only after
  successful submission. Its state directory has no stamp files. Repeated
  failed attempts remain eligible, as intended. The accessible journal proves
  Plesk submission attempts and exit status, but omits the rejection reason.
  Protected mail diagnostics are needed before choosing a sender/configuration
  correction. No message was sent by this investigation, and receipt, success
  suppression, and drill-route coverage remain unverified.

`id` and `sudo -n -l` confirm the existing account has neither system-journal
membership nor sudo authorization. Do not use unrelated accounts or Docker to
work around this boundary. Required next inputs are host-owner read access or
redacted extracts for the October 13 rotation failure and October 15 mail
submissions, followed by review of a concrete correction and authorization for
a harmless test notification through the actual route.

## Demonstrated additional caller defect — implementation next

Tracing LR-18 consumers found `spell_teleport`, `spell_depart`, and
`spell_etheric_gust` unconditionally return inside `LIMITED_TELEPORT_ZONE` even
when `how_close()` reports a reachable destination within five rooms. Their
truthiness check also treats a valid positive distance as failure. The zone
restriction is virtual rooms 5700–5999. This is independent of attribution of
the original 37 diagnostics. Reproduce it using the existing real-graph harness
and actual spell bodies, then retain the five-room restriction while allowing
successful in-range movement. Keep this repair in a separate focused PR.

## Verification and publication

Read-only evidence checks above are complete. No production configuration,
services, logs, player files, or notification state were changed. C/C++ is
unchanged at this checkpoint; build/runtime proof is due with the caller repair.
Do not close #106 while its missing historical/operational acceptance remains.
