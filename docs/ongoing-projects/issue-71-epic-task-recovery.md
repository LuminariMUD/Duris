# Epic task recovery — issue #71

Issue: <https://github.com/LuminariMUD/Duris/issues/71>

## Outcome and boundaries

Restore the data/readiness paths needed by earned epic tasks, preserving the
already-paid epics, saved pending task, completed-zone exclusions, and the
independent 95% zone / 5% alternative roll from merged PR #72. Leave each code/data
preparation chunk tested, pushed, and ready for review. Keep this document current.

Production investigation is read-only. Deployment, database updates, migrations,
restarts and live player mutations require separate authorization. Do not guess
task eligibility from epic payouts or stone placement. Do not close #71 until its
production recovery journey is proven.

## Current evidence (2026-10-16)

- Base: `b149b3ada6e8c9c1e041ad864772195173fef7c6`; isolated checkout
  `/home/aiwithapex/projects/duris-issue71`, branch `branch/issue-71-task-catalog`.
  The main checkout has unrelated issue #110 work and is left alone.
- Production access: existing SSH alias `duris-staging`, checkout
  `/home/staging/duris`. Despite the alias, `.env` says `ENVIRONMENT=production`,
  `PERSISTENCE_MODE=mariadb-primary`; database `duris_prod`.
- Production checkout HEAD matches the base. Running PID 2460411 started at
  host time `2026-10-16 04:23:33`; running executable equals installed `dms`,
  SHA-256 `e80be97368fd6ef7253547db4ba8565a7fc066ebc1cd11509b442452b89d84c6`.
  Backend stamp: `mariadb/production`. Git HEAD alone does not prove the binary's
  exact source revision; the live logs below prove the pending/catalogue paths run.
- Live read-only SQL: 350 zone rows, **0 enabled task rows / 0 distinct task
  zones**, no enabled duplicates, empty enabled roster. This confirms missing
  catalogue flags as a global blocker.
- `lib/duris.properties`: `epic.errandStep=500.000` (compiled default is 200).
- `logs/log/status` (host timestamps, retained without player identities):
  - 04:23:37: catalogue unavailable/invalid at boot.
  - 04:24:54, 05:24:58, 06:25:02, 07:25:06: refresh rejected,
    `candidate_zones=0 retained_zones=0`.
  - 05:22:56: assignment deferred,
    `catalog_ready=0 zones=0 player_reads_ready=0`.
  The last value establishes a second readiness symptom; fixing flags alone may
  not repair this character. No identity correlation with the original reporter
  has been established.
- Live saved-affect aggregate: 22 characters have `TAG_EPIC_TASK_PENDING` (2128),
  nine have an active `TAG_EPIC_ERRAND` (2022). No player names/IDs are retained here.

## Plan and ablation

1. Trace the live `player_reads_ready=0` symptom through new-character creation,
   ordinary login/materialization and state resets. Fix a demonstrated missing
   initialization path with a focused executable regression and server build.
2. Recover the curated task roster from an authoritative retained source. Prepare
   a narrow, reviewed, rerunnable provisioning artifact and disposable-database
   verification if that source can be established. Never infer the roster from
   the separate payout seed. Record any unresolved roster decision explicitly.
3. Add only the catalogue diagnostics needed to distinguish empty flags, invalid
   IDs, database failures and player unavailability. Verify cold boot, failed
   refresh retention and actual paged maintenance publication; repair demonstrated
   defects in that path. Reuse existing tests and interfaces.
4. Keep local proof separate from live acceptance. Prepare concrete production
   remediation for approval only after all independently authorized work is ready.

Files: relevant player initialization, `src/world/epic_task_catalog.*`, its
maintenance callers only where necessary, existing focused regressions, the
reviewed roster/provisioning documentation, and this continuation record.

Proof: existing `test_set_based_gameplay_reads.py` and relevant player-load/
maintenance tests; new regression cases for reproduced gaps; disposable DB and
connected-character journey where possible; `make -C src`, touched-code format
checks and `git diff --check`. Retain exact results below as they complete.

The existing pending-affect mechanism already satisfies retry/persistence policy.
No replacement queue, alternative task fallback, new timer, broad eligibility
enablement, or unrelated cleanup is planned.

## Continuation checklist

- [x] Read issue body/comments and merged #72 behavior; preserve existing work.
- [x] Read-only production catalogue/log/configuration investigation.
- [x] Reproduce first-session readiness gap and complete targeted code repair
  (not yet correlated to the original reporter).
- [x] Recover historical curated roster (107 enabled zones); correction preparation
  and current-world validation remain in progress.
- [ ] Verify cold boot and scheduled refresh, including last-good retention.
- [ ] Publish focused PRs as chunks pass local checks.
- [ ] Separately authorized production correction/deployment and already-pending
  recovery without another award; save/rent/relogin/restart acceptance.
- [ ] Publish production acceptance before issue closure.

## Checks and publication

Chunk 1 initializes empty gameplay history in the shared `init_char()` used by
telnet, WebSocket and staff creation. Existing logins still publish durable
history through `player_load_materialize()`; no blanket reset is added on entry.

- Before repair, the extended real-function regression aborted on
  `pc.gameplay_reads.status == gameplay_read_status::ready` immediately after
  `init_char()`. Existing tests had initialized that state themselves.
- `python3 tests/async/test_set_based_gameplay_reads.py` — PASS after repair;
  ASan/UBSan exercises real initialization and both award callbacks, 100 + 400
  earned epics at threshold 500, first-session completed-zone exclusion, pending
  save/restore/retry, exhaustion, and all 20 initial selection rolls.
- `python3 tests/async/test_character_persistence_gap.py` — PASS (source contract).
- `make -C src -j4 CC='ccache g++'` — PASS, MariaDB/development server linked.
- `./scripts/format.sh --check`,
  `./scripts/format.sh --file src/account/nanny.c --check`, and
  `git diff --check` — PASS.

No production writes or restart performed. Connected-player and production
acceptance remain outstanding; a callback/snapshot harness is not that evidence.

## Reproduction notes

Read production credentials from the protected `.env` without printing them.
The password key is `DB_PASSWD`, not `DB_PASSWORD`. Use `rg --no-ignore` when
reading ignored production logs. Query `zones WHERE task_zone=1`, including count,
distinct count, duplicate grouping and ordered roster. Player state is in
`player_affects`; use aggregate counts instead of public identities.

Potential roster sources: retained production SQL dumps under
`/home/staging/backups/duris`, plus the historical 2026-06-23 dump referenced in
`docs/operations/EPIC_ZONE_SEED.md`. Inspect only zone configuration, never publish
the database dump or player/account data.

The supplied production archive is retained on production at
`/home/staging/duris/tmp/DurisMUD-production-database-2026-07-12.tar.xz` (not in
this local checkout). Read-only extraction confirmed SHA-256
`e3bfb5de3348f04893fc0916e9da6b7095ff0b7d184f34903815d1c9f649b9a7`, member
`prod.sql`, footer `Dump completed on 2026-06-23 23:24:20`, and 355 unique zone
rows, of which 107 explicitly have `task_zone=1`. Only zone number/name/eligibility
was extracted to ignored `bin/analysis/historical-task-zones.json`. Historical
eligibility still needs comparison with the currently loaded world before use.
