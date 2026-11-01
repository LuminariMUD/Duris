# Issue #498: small server delivery for Mudlet #26

Updated 2026-11-01. **Revised delivery completed and ready for review.**
This completes the selected first delivery, not all candidates in
[server #498](https://github.com/LuminariMUD/Duris/issues/498) or
[client #26](https://github.com/LuminariMUD/duris-client/issues/26).

## Outcome and scope

Provide structured time, session boundaries, combat target/tank and outgoing
applied damage, and visible owner inventory/equipment. Reuse existing values,
flushes and publishers, with bounded optional work and a concrete client handoff.
No action/cooldown framework, extra storage calls or broad qualification campaign.

1. Time/capabilities and session/combat: server PRs
   [#542](https://github.com/LuminariMUD/Duris/pull/542),
   [#544](https://github.com/LuminariMUD/Duris/pull/544),
   [#545](https://github.com/LuminariMUD/Duris/pull/545) and
   [#546](https://github.com/LuminariMUD/Duris/pull/546) are merged into master.
2. Owner items: [#547](https://github.com/LuminariMUD/Duris/pull/547) is ready
   against master. It includes bounded pages, native selectors, requested nested
   contents, epoch/access cancellation and completed publication. Uninterested/
   unchanged lists build no JSON. Open/close, transfer, editor, condition and
   rename owners notify; knockout and reveal-true-name review findings are fixed.
3. Cost evidence: [#548](https://github.com/LuminariMUD/Duris/pull/548) is stacked
   on #547. Three lines add `gmcp_protocol` to the existing tracer before storage
   work. The [wire document](../network/GMCP.md#short-local-cost-check--2026-11-01)
   records the short matched results and their limits. No new measurement service.
4. Client handoff: [client #28](https://github.com/LuminariMUD/duris-client/pull/28)
   is ready against `branch/protocol-interface-improvements`. It provides real
   generated fixtures, source selection/fallback and page/lifecycle rules, and
   points to existing ship, status/vitals, affects, quest and chat packets.
   Client UI/automation adoption is separate from this server delivery.

## Proof and stopping rule

**Files:** GMCP/item publication/presentation owners and existing focused tests;
three-line timing attribution; wire/plan docs; client capture/fixtures/handoff.
**Non-goals:** deployment, release tag, production operations, full burn-in,
CI wait, client runtime migration or completing every candidate in the issues.
**Proof:** reuse valid recorded results; the required affected checks below pass.
No further regression/hardening phase is required for this selected delivery.

- Both backend builds passed after parent integration and the focused review fixes:
  `make -C src -j4`; separate `PERSISTENCE_BACKEND=flatfile` build to
  `bin/server/dms_flatfile`. Formatting/normal changed-line tidy hooks passed.
- `python3 tests/async/test_gui_gmcp_contract.py --sanitize`: both transports,
  bounded 3,000-item pages/search, 100-descriptor fairness, selectors, access,
  editor/queue/allocation retry, disarm/repair/temporary-save and committed reward
  retry/replay/logout. Review regressions cover knockout recovery and both true-name
  rename paths. Parser fuzz's 11,540,402 sanitizer executions remain valid:
  later changes do not change item parsing.
- `python3 tests/async/test_gmcp_control_journey.py --server bin/server/dms_flatfile`:
  normal Telnet/WebSocket dispatch, lifecycle, combat and native item commands pass.
  The merged parent's WebSocket regression and reward-publication tests pass.
- Focused `run_world_quest_dual_backend.py` gameplay leg (`11:2`, one ASK quest and
  restart per backend) passed on MariaDB and flatfile after reward-batch integration.
  Container audit/access/capacity refusal, crumbleloot, player-load and documentation
  checks passed. Their unchanged paths were not rerun unnecessarily.
- Short cost check: five approximately 75-second windows per binary, one descriptor,
  3,000 objects, idle/uninterested, disabled, combat, subscribed items and slow reader.
  Zero overruns; delivery protocol max 669 us; whole-tick max 1.078 ms. See the wire
  document for averages, source/binary hashes, memory behavior and limitations.
- `python3 scripts/capture_server_gmcp.py --server /home/aiwithapex/projects/duris-issue-498`
  in the client handoff checkout: producer passed; 25 source hashes match and 12
  phases include the new contracts plus existing populated/clear cases.
- Real Mudlet `python3 scripts/mudlet_test.py run --scenario server-wire` passed
  (`20261101T102603Z-38eccfe8-server-wire`); populated/clear screenshots inspected.
  The stale target-HP test expectation was corrected to the captured 32 percent.
  This proves existing wire decode/clears, not adoption of new handlers or an HP
  widget symptom fix. Fixture/docs-only work needs no package release/version bump.

Ablation: retained the useful implemented interfaces, their focused proof and
one small cost check; removed the requirement to finish all future candidates
before publishing. Every delivered chunk is committed, pushed and in a review PR.

## Handoff and remaining follow-ups

Server worktree: `/home/aiwithapex/projects/duris-issue-498`.
Item branch: `branch/issue-498-owner-items` (review fixes `524949722`).
Current branch: `branch/issue-498-delivery-evidence` (#548).
Client handoff worktree: `/home/aiwithapex/projects/durisclient-issue26-server-handoff`,
branch `branch/issue-26-server-handoff` (fixture fix `2115d9b`).
Other checkouts/dirty work and the original reference are preserved. Parent-merge
cleanup was performed by another agent; do not recreate deleted parent branches.
No merge of the three new PRs, production operation or release tag is part of this goal.

Local ignored proof: `bin/qualification/issue498/owner-items-parent-wire.json`,
`owner-items-parent-*-restore.json`, `owner-review-*.log`, `delivery-*.log`,
`short-cost/{run.py,baseline.json,feature.json,*-latency.log}`. The original
`baseline-881/` remains intact; the matching client-free reference build lives
under `short-cost/baseline-flatfile/`. World generation is shared: prepare once,
then run isolated backend legs. Do not run `make world` concurrently.

WHO, scan, dice and identify remain possible small authorized-command-result PRs.
Actions, cooldown/activity tracking, richer score/skills, affect reasons, observer
notices, epic reports, weather and chargen extensions are deferred. Select a real
client consumer before adding any. Preserve text fallback for unavailable features.
The reported player/pet/opponent HP symptom remains unverified in a real game.
Review/merge/deployment and these follow-ups are separate work, not missing steps
in the completed revised server delivery.
