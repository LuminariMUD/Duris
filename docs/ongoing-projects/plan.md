# Issue #264: supervised pwipe completion

Updated 2026-10-24. Implementation and local qualification are complete for the supervised
procedure below. Production operations and PR merging are not authorized.

## Scope and finish line

One supervised MariaDB-primary wipe: drain accepted external work, stop external
writers and competing service supervision, run the existing launcher as the game
user, and explicitly start the new season only after durable completion.
Incomplete resets remain fenced; use the existing same-epoch recovery or matched
restore procedure. Never run checkout qualification scripts through sudo.

Reset every account-bank balance. Recreate only eligible exact level-62 Overlords
with clean bodies and new PIDs; blocked/deleted characters remain excluded, even
with stale account projections. Preserve accounts, bans, approved benefits,
configuration and recovery/history evidence. Old seasonal state must not return;
retries must not apply or decrement carryovers twice.

No new PRs, privileged helper, unattended wipe service, flat-file wipe support,
platform matrix, repository-wide burn-in, broad cleanup or optional hardening.
The owner explicitly narrowed #264 to this supervised procedure.

## Delivered changes

- Existing server [PR #363](https://github.com/LuminariMUD/Duris/pull/363) and
  [DurisWeb #97](https://github.com/LuminariMUD/DurisWeb/pull/97) target master.
  The existing stacks are consolidated into these candidates; this task created
  no PRs and merged no PRs.
- Removed root-required systemd qualification and the forced Git safe-directory
  bypass. The removed mode rejects before resource creation. Existing production
  service behavior is unchanged; historical systemd proof remains historical.
- Restored-world assertions now check the frozen generation immediately after
  first boot and a fresh generation independently after second boot. Each reads
  the current boot's full log, because the launcher rotates logs at every boot.
- DurisWeb probe waits for durable donation acknowledgement with its existing
  bounded waiter. Literal loopback matching already passed on the published head.
  Repair published as `efc9de3`; no player-visible release news is needed.
- Security finding fixed in `da08e1812`: exclude blocked mappings by PID or name
  from staff recreation. The existing native regression covers blocked current-name
  and stale-name mappings, alongside missing/stale/wrong-owner eligible mappings.
- Runbook and regression guidance describe the supported supervised procedure.

## Acceptance evidence

1. **Contract/runbook:** lifecycle validator covers 200 SQL tables, 35 other stores
   and 42 Redis surfaces. Fourteen lifecycle tests, thirteen reset-manifest checks
   and SQL completion checks pass. The manifest, existing consumer proof and
   runbook describe the same reset/preservation policy.
2. **Actual new-season journey: passed.** Revision `1ca00c651`, production binary
   SHA-256 `775c89a6637ad84b544bd41ac0f102754fa32080d7390d23c2ae4811ec90569b`.
   The 301.44-second real countdown, launcher/filesystem cleanup, Redis isolation,
   Overlord login, fresh mortal combat/loot, rewards, save, reconnect and second
   boot passed. Command:
   `python3 tests/async/run_pwipe_runtime_journey.py --redis --restore /home/aiwithapex/projects/duris-issue264-finish/bin/qualification-production/server/dms_new`.
3. **Recovery: passed.** The same run restored a frozen matched SQL/journal,
   filesystem and authenticated Redis generation. First-boot generation,
   original account/body/bank/reward/items, fresh checkpoint and independent
   second-boot recovery passed; source SQL/files/Redis and generation hashes
   remained unchanged. Session 91866 exited 0. Evidence:
   `bin/analysis/pwipe-integrated-restore.log` and
   `bin/analysis/pwipe-runtime-mariadb-redis-restore.json`.
   An earlier assertion failed because it sliced an offset from rotated/bounded
   diagnostics; its report is preserved as `pwipe-restore-first-attempt.json`.
4. **Findings:** the blocked-roster repair passed the production build and actual
   native MariaDB SQL/launcher/recovery suite, including unchanged missing/stale
   projection repair and stable retry roster. Command:
   `python3 tests/async/run_pwipe_handoff_mysql.py --server /home/aiwithapex/projects/duris-issue264-finish/bin/qualification-production/server/dms_new`.
   Logs: `bin/analysis/pwipe-blocked-{build,native,hook}.log`. Session 69736 exited 0.
   The security thread is resolved. The eligibility-only change retains the
   successful ordinary-staff gameplay/restore evidence.

Reuse the [published evidence record](https://github.com/LuminariMUD/Duris/blob/10acd11765059ec3f158da0b9665a45696bff91f/docs/ongoing-projects/plan.md)
for completed both-engine native/failure matrices, writer/replay isolation,
Redis off/on/failure/re-enable, reward preserve/discard/claims, flat-file rejection,
telemetry manual cutover and paired website HTTP/WebSocket/donation proof.
Final MariaDB/MySQL logs were rechecked and retain passing ambiguous-commit,
same-epoch recovery, residual-store fencing and staff ownership/clock assertions.
No fresh matrix is required for unchanged behavior.

Website format, lint, type-check, build, two donation suites/nine tests, and actual
compiled principal/delayed-ACK/timeout checks pass. Both review threads are resolved;
code and security reviews completed without findings at `efc9de3`.

Known ancestor dispositions in the consolidated source:
#309 consumers -> #361/original repair; #310 preflight reaper -> recorded child
status; #311 reset SQL -> synchronous owning connection; #313 staff mapping/clocks
-> durable ownership and fresh clocks; #339/#352 recovery parents/access -> guarded
preflight; #330 -> unsafe qualifier removed; #337 -> independent restored-boot
proof above. Superseded intermediate heads are not individually repaired.

## Final integration checks

Reconciled master through `c753a4806`, preserving the tested wipe source, launcher,
runtime qualifier, blocked-roster regression and native handoff behavior. Removed
the reintroduced systemd helper/mode from the candidate as required by this plan;
the original paused drafts remain intact. Independent upstream changes are retained.

The final production build passes at `5943e287b` with:
`make -C src -j8 PERSISTENCE_BACKEND=mariadb BUILD_PROFILE=production BIN_ROOT=/home/aiwithapex/projects/duris-issue264-finish/bin/qualification-production`.
Log: `bin/analysis/pwipe-333-build.log`; session 99985 exited 0.
Binary SHA-256: `b282e1d4cee26eab5c758f4317c5ec41acf835e1e70f3cba30b474082511b4bc`.
Copied dependency records were relocated before this build; all affected headers
and sources were rebuilt. The later reconciliation changes only a migration test
and regression documentation: all 24 migration-runner tests pass, and production
source/binary are unchanged. The incoming training-dummy regression also passed.

Formatting and commit hooks pass with Clang 18 and GCC 13 headers; no hook bypass.
Both final PRs have zero unresolved findings. Server code and security review
completed without findings at `6eb10fae6`; the subsequent upstream reconciliation
preserves that wipe implementation byte-for-byte. Website review passed at
`efc9de3`. A final source/diff review confirms the removed privilege workflow,
separate restored-boot assertions, blocked-roster exclusion and preserved upstream
changes. Later automated runs may inspect ancestry/documentation updates; they are
not represented as already completed.

Technical qualification is complete at this candidate. The separate process that
continues merging ancestors may create new base conflicts; those are subsequent
integration work, not grounds to repeat unchanged runtime proof. No production
acceptance or ongoing guarantee about a changing master tree is claimed.
Do not add another PR, matrix, helper, full countdown or optional hardening phase.

## Preserved work and limits

Implementation checkout: `/home/aiwithapex/projects/duris-issue264-finish`, existing
branch `branch/issue-264-overlord-projection-repair`. Website checkout:
`/home/aiwithapex/projects/durisweb-issue264-presence`.
The primary checkout and paused `duris-issue264-plan` drafts, including the unused
privileged-helper draft, remain untouched. The original plan-only worktree also
remains available. The [stopped checkpoint](https://github.com/LuminariMUD/Duris/blob/2d8948bd3/docs/ongoing-projects/plan.md)
records their exact paths and files.

This qualification does not claim production acceptance, unattended systemd
qualification, flat-file wipe support or rendered-browser coverage. Production
wipe/deployment and closing/merging superseded PRs remain separate authorized work.
