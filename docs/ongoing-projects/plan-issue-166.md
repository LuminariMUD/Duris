# Issue #166: Hatred repair and lifecycle validation

Tracking: [issue #166](https://github.com/LuminariMUD/Duris/issues/166).
Review order: [#209](https://github.com/LuminariMUD/Duris/pull/209) ->
[#210](https://github.com/LuminariMUD/Duris/pull/210) ->
[#212](https://github.com/LuminariMUD/Duris/pull/212).

## Behavior and implementation

An eligible level-21 Mountain Dwarf receives exactly one combat-pulse `-1`
modifier and one spell-pulse `-1` modifier while a visible Orc, Duergar, or Drow
occupies the same room. Preserve actual-race matching, existing sight rules,
NPC and player targets, and the existing periodic check cadence.
Activation and subsidence each announce once per transition; unchanged state and
repair of a malformed pair remain silent.

- #209 bounds the existing race-table search, repairs partial/duplicate affects,
  and removes effects without accessing released nodes.
- #210 makes the pair transient and owned by one recoverable watcher. It covers
  normal entry, online unlock, temporary ineligibility, copyover recovery,
  scheduling refusal, cancellation, and the existing timer's pulse units/default.
- #212 qualifies the entry and persistence wiring with a disposable running-server
  journey on both backends, alongside the focused tests in #209/#210. Its MariaDB
  leg remains in `make test-db`. Cleanup checks the exit status even if the server
  has already crashed, including during client closure.

The refreshed gameplay implementation is `b7af19f2f34e172ecaaec3dced9c5f3d74620da4`
(#210), carrying master `d5329e66b` with the original Hatred changes preserved.
This validation PR changes no gameplay code, schema, or configuration.

## Focused proof

[The Hatred harness](../../tests/async/test_innate_hatred.py) executes production
matching, eligibility, visibility, affect mutation/messaging, expiration,
scheduling, and legacy serialization under ASan/UBSan. Its ten modes cover:

- Bounds, ordinary and hated races, same-room selection, NPC/player targets,
  level/transformation eligibility, and visibility.
- Exact paired pulse contributions, one-time messages, silent normalization,
  and preservation of unrelated affects.
- Repeated entry, one successor, delayed checks across affect ticks,
  scheduling refusal, temporary eligibility recovery, and owner cancellation.
- Omission of transient Hatred effects from the legacy writer.

[The snapshot regression](../../tests/async/test_player_snapshot_capture.py)
checks that real snapshot capture omits both Hatred effects while retaining an
unrelated saved affect. Existing wear-off, Reflection, race-help, and scheduler
tests are adjacent controls. These harnesses do not execute normal login,
copyover recovery, or either backend's player restore path.

[The server journey](../../tests/async/run_innate_hatred_journey.py) reuses the
existing disposable scene, client, and backend support. It exercises ordinary
login, online unlock, all three enemy races, unrelated/empty rooms, movement,
visibility, sustained presence across two affect ticks, linkdead reconnect,
copyover, rent/relogin, cold restart, and death/extraction. It inspects the actual
paired modifiers and single watcher; the MariaDB leg also verifies that saving
does not persist Hatred rows. It never reads the checkout's `.env` or uses an
existing game/database.

[The shutdown regression](../../tests/async/test_innate_hatred_journey.py) uses
real child processes to cover clean shutdown, a crash before cleanup, and a
crash during client closure, plus cleanup before a process exists. Both crash
cases reproduced the old false success before the exit-status check was fixed.

Run from the worktree root:

```sh
python3 tests/async/test_innate_hatred.py
python3 tests/async/test_innate_hatred_journey.py
python3 tests/async/test_player_snapshot_capture.py
python3 tests/async/test_affect_wear_off_message_contract.py
python3 tests/async/test_innate_reflection.py
python3 tests/async/test_race_innate_help_sync.py
python3 tests/async/test_nevent_scheduler_runtime.py
python3 tests/async/test_nevent_cancellation_runtime.py
make -C src -j4 -W classes/innates.c
make -C src -j4 -W classes/innates.c PERSISTENCE_BACKEND=flatfile DMS_BINARY=../bin/server/dms_hatred_flatfile
python3 tests/async/run_innate_hatred_journey.py --backend flatfile --server bin/server/dms_hatred_flatfile --output bin/analysis/pr212/flatfile-final.json
tests/async/with_disposable_mariadb.sh python3 tests/async/run_innate_hatred_journey.py --backend mariadb --server bin/server/dms_new --output bin/analysis/pr212/mariadb-final.json
make test-list TEST_MATCH=innate_hatred
bash -n tests/run_db_tests.sh
./scripts/format.sh --check
git diff --check
```

On 2026-10-19, all ten native ASan/UBSan Hatred modes, four shutdown regressions,
snapshot capture, and the adjacent controls passed. Both server builds passed
on the final gameplay source, forcing recompilation of `innates.c` and relinking
so the later `d7325b0a` change is included. After master advanced, both builds and
the incoming epic-stone/training regressions passed again on the refreshed tree.
The Hatred source and focused test inputs were unchanged by that integration.
Both Hatred tests are discoverable by the ordinary runner.

Both refreshed backend journeys passed, each spanning 600 game pulses and two
actual affect-tick boundaries. Login, reconnect, copyover, rent/relogin, cold
restart, and death/extraction all passed with the expected pair and watcher.
Build logs and full journey JSON/logs are retained under ignored
`bin/analysis/pr212/`; the `*-final.json` files record binary hashes, source SHA,
NPC definitions, modifiers, watcher counts, and transition message counts.

The independent stale root-runner expectation was repaired separately in
[#211](https://github.com/LuminariMUD/Duris/pull/211), which landed during these
journeys. After carrying that test-only commit forward,
`python3 tests/async/test_root_test_harness.py` passed directly, including
timeout/process cleanup coverage. The final runtime inputs are identical to the
qualified tree, so those server results remain valid. No full regression-suite
or hosted-CI success is claimed.

## Git handoff

Master advanced during qualification. Its gameplay changes and then #211's
test-only repair were merged into #209, now `b071b9f5b`, preserving its earlier
merge resolution and both unrelated plans. #210 was rebased onto that head with
both Hatred patches unchanged by range-diff; #212 was rebased and consolidated
into one validation commit. Keep the order #209 -> #210 -> #212. No release tag
is needed. Use squash
merges for master's linear history and carry each dependent PR onto master after
its parent lands, preserving only that PR's remaining diff. Refresh refs and
check the resulting tree at each landing. This work leaves the stack open for merge.

## Remaining live report

The reported production "any NPC" activation still lacks an offending NPC's
actual race/VNUM and a concrete trigger trace. The reproduced bounds, cleanup,
and partial-pair defects do not by themselves establish its sole root cause.
Keep #166 open while that evidence is missing. Production diagnosis, deployment,
and confirmation of the original symptom remain separate from local patch proof.

The earlier unrelated plans remain preserved in
[issue-67-artifact-identity-plan.md](issue-67-artifact-identity-plan.md) and
[plan-issue-57.md](plan-issue-57.md).
