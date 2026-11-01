# Issue #498 pause handoff — 2026-11-01

**Paused at owner request.** The full seven-part objective remains open. The
[current plan](plan.md) retains scope and acceptance criteria; this note records
where to resume. Work only in `/home/aiwithapex/projects/duris-issue-498` on
`branch/issue-498-owner-items` (`origin` tracks it). The chat's default Duris
checkout has unrelated staged work and must be left alone. Another clean worktree,
`/home/aiwithapex/projects/duris-issue-498-controls-review`, holds the published
event parent. The detached `duris-issue-498-baseline` reference remains at
`881853d21` for later matched measurements. Current `origin/master` was checked
at `881853d21`; that commit is already in the feature stack. Do not touch
production or run migrations.

Four focused PRs are ready for review in order: [#542 control/time](https://github.com/LuminariMUD/Duris/pull/542) →
[#544 Session/copyover](https://github.com/LuminariMUD/Duris/pull/544) →
[#545 combat target/tank](https://github.com/LuminariMUD/Duris/pull/545) →
[#546 applied damage](https://github.com/LuminariMUD/Duris/pull/546).
The Session NPC-bootstrap finding is fixed and its review thread resolved.
The shared truncated-color formatter fix is on #545, and #546 has merged its
updated parent. #546 was mergeable when last checked. CI was not awaited.
No PR exists yet for owner items; its branch is a pushed **WIP checkpoint**.

The owner branch has bounded, opt-in inventory/equipment pages, snapshot-scoped
selectors through native item lookups, independent mutation epochs, editor
lifetime guards, and presentation notifications at ownership, container, rename,
condition, and visible-flag owners. The formatter reads live objects only; it
neither invokes text commands nor reads SQL. The [wire draft](../network/GMCP.md)
records implemented top-level behavior and explicitly excludes nested requests.
These changes have not been accepted as the complete item feature.

Verified on the current owner worktree: MariaDB and client-free flatfile builds;
`python3 tests/async/test_gui_gmcp_contract.py --sanitize` for both transports,
3,000 duplicates, 100 descriptors, stale selectors, bounded/failing pages and
editor transfers; `python3 tests/async/test_gmcp_control_journey.py --server
bin/server/dms_flatfile` for disposable Telnet/WebSocket item commands,
subscription/resync and lifecycle; committed world-quest reward publication,
locker/container weight, fired-missile, color-stripping, and documentation
regressions. Logs and JSON evidence are under ignored
`bin/qualification/issue498/`, notably `owner-items-editor-wire.json`.
The GMCP input fuzzer passed 2,320,344 sanitizer executions on the current
owner-item source; run it again if protocol/parser code changes on resume.
No real Mudlet behavior or matched overhead result is claimed.

Resume with the remaining item acceptance cases: explicitly requested nested
contents using current owner, visibility, closed-container and private-locker
gates; cancel pending pages on access change; exercise get-all, give, wear,
repair/rename, refused audits, save/load, SQL and flatfile restore, deferred
quest-reward success/failure/replay, and owner logout before publication.
Confirm one completed visible revision after a durable reward retry and no
transient terminal-save unequip. Then run the relevant sanitizer, booted and
backend tests, update the wire contract/plan, and open the owner-items PR
against `branch/issue-498-combat-events` only when that chunk is review-ready.
Resolve any new parent review findings on their owning branch and merge them
forward carefully.

After items, the original plan still requires semantic actions/activity/cooldowns,
authorized scan/ship/dice/identify/WHO results, real durisclient/Mudlet fixtures
and UI proof under client issue #26, and matched baseline/pulse/flush/RSS/slow-
consumer qualification. The reference binary/metadata live under
`bin/qualification/issue498/baseline-881/`. The reported HP widget symptom remains
unverified in a real client. No deployment, release tag or production operation
has been performed.
