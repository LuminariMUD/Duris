# Issue #264: shortest path to finish

Updated 2026-10-24. **Implementation resumed by owner request; qualification remains open.**
Plan branch: `branch/issue-264-pwipe-qualification`.
Issue: [#264](https://github.com/LuminariMUD/Duris/issues/264).
The owner's latest instruction permits narrowing #264 to finish quickly. This plan
supersedes the original W1–W7 schedule, estimates, helper project and repeated
qualification gates. No new PRs are planned.

## Finish line and hard scope limit

**Outcome:** a supervised MariaDB-primary wipe that clears the agreed seasonal
state, preserves approved carryovers, stays fenced if incomplete, and reaches
fresh gameplay/save/reconnect/reboot with a working recovery route.

Keep the settled policy: **reset every account-bank balance; recreate only exact
level-62 Overlords**, under their preserved accounts with new PIDs and clean
seasonal assets/progression. Preserve accounts, bans, approved account benefits,
backups, history and configuration according to the existing reset contract.
Rewards cannot be applied/decremented twice; old characters/items/world state
cannot return. These are completion requirements.

**Supported procedure:** planned downtime, drain accepted work and stop external
writers and service supervision, the existing launcher operated as the game user, the
real pwipe command, then an explicit fresh start. Keep competing launchers stopped
through reset/recovery; restart the normal service and integrations only after
durable completion and the documented cutover. Reuse the existing runbook's
same-epoch resume and matched-restore procedures. No online/zero-downtime wipe or
unattended orchestration is required.

**Non-goals:** new features, services, privileged helpers, frameworks, backend
parity, extra platform/version matrices, general security/persistence cleanup,
repository-wide burn-in, rendered-browser acceptance, production deployment/wipe.
Unrelated findings do not create work in this task. Existing blocking findings
still require a disposition; required review is not waived.

**Files now:** only `docs/ongoing-projects/plan.md`.
**Files when resumed:** existing runtime qualifier, the two existing DurisWeb probe
fixes, and their directly affected runbook/regression guidance. No production
C/C++ or schema work is currently planned. Add such work only for a reproduced
failure of the supported procedure, with its smallest regression.
**Proof:** reuse recorded valid results; repair the known restore assertion and
run that affected journey once. Details below.

## Reuse what already exists

Live GitHub checked 2026-10-24: server [PR #363](https://github.com/LuminariMUD/Duris/pull/363)
is open at `10acd11765059ec3f158da0b9665a45696bff91f`; companion
[DurisWeb #97](https://github.com/LuminariMUD/DurisWeb/pull/97) is open at
`c4772780bb998a52fb379effdd01b26d29f95ca5`. Both remain stacked. This is not
a merge/readiness claim.

The [published evidence record](https://github.com/LuminariMUD/Duris/blob/10acd11765059ec3f158da0b9665a45696bff91f/docs/ongoing-projects/plan.md)
holds completed changes, commands, revisions and results. The
[stopped checkpoint](https://github.com/LuminariMUD/Duris/blob/2d8948bd3/docs/ongoing-projects/plan.md)
preserves unpublished state and remaining findings. Use these records; do not
copy their chronological history back into this plan or turn completed work into
new checkboxes.

Reuse the recorded inventory/consumer work, both-engine native SQL/launcher/failure
matrices, writer/replay fences, real countdown/operator/gameplay journeys,
Redis off/on/failure/re-enable cases, reward preserve/discard/claim cases,
telemetry manual cutover, website HTTP/WebSocket/donation cutover, flat-file
rejection, and maintained builds. Later changes invalidate only affected evidence.

The final recorded production-profile binary SHA-256 is
`de2aa15f93bc9afe9e50d74888439d5b3bc5f1714d588ede1a6135effaf1a7c4`.
Confirm the reused binary matches it before the remaining run; do not rebuild
unchanged C/C++. The paused qualifier draft has no `src/` changes.

Do not count the interrupted ordinary-user systemd run as a pass. Earlier actual
service exit-55/58 evidence remains historical coverage; the production unit's
restart policy is unchanged. A newly secured automated systemd harness is outside
this narrowed completion scope.

## Remaining work — three steps, then stop

Implementation is authorized for these steps. Production operations and merging remain separate.

Current progress: isolated the existing #363 branch in
`/home/aiwithapex/projects/duris-issue264-finish`, preserving all stopped drafts.
Repaired #337 to assert the frozen generation immediately after first boot and
the newly saved generation in an independent second-boot log window. Python
compilation and `git diff --check` pass; runtime proof is still pending.
Removed the root-required systemd qualifier and forced Git safe-directory bypass;
updated regression guidance and the supervised runbook. The existing production
binary matches the recorded SHA-256. The direct Redis/matched-restore run is live
in execution session 69369, logging to `bin/analysis/pwipe-final-restore.log`.
Poll that session before starting another run; an empty early log is not failure.
Both existing tip PRs now target master. Website format, lint, type-check, build,
two donation suites/nine tests, and the compiled principal/delayed-ACK/timeout
probe check pass on the current source. The literal principal expression was
already correct at the published head; only the durable ACK repair needs a commit.
The running restore journey passed operator checks and entered its real countdown.
Server master has one additional deployment commit `4b4fec518`; integration must
preserve its migration-runner, news and build repairs before final publication.
Integration inspection: `git merge-tree --write-tree HEAD origin/master` succeeds
without conflicts in both repositories; no branch merge/rebase is needed to repair
integration. Normal final merging preserves master's deployment changes.
Website repair is published as `efc9de3`; both #97 review threads are resolved
after the compiled probe checks. Server qualifier repair is published as `622a6604b`.
Current inventory proof passes: 200 SQL tables, 35 other stores, 42 Redis surfaces;
14 lifecycle tests, 13 reset-manifest checks and SQL completion checks pass.
Existing final MariaDB/MySQL native logs still record successful ambiguous-commit,
same-epoch recovery, residual-store fencing and staff ownership/clock assertions.
Known ancestor findings were checked against the consolidated source: preflight
uses `take_reaped_child_status`; reset zone SQL uses synchronous `qry`; staff use
durable ownership and initialized clocks; wiper rejects nested cleared parents and
checks maintenance ancestor search permissions before treating files as absent.
Those intermediate PR heads remain superseded, not individually repaired or merged.

### 1. Finish from one candidate per repository

Use the existing server stack tip (#363) and existing companion tip (#97).
Retarget those existing PRs to their repository's current master when implementation
resumes; inspect their cumulative diffs once and resolve only actual integration
conflicts. Keep required predecessor fixes. Do not replay, rebase, backport, test
or merge every ancestor separately. Do not create another successor PR.

Carry this corrected plan into the server candidate. Apply the small remaining
fixes directly to those candidates. For the #310 plan conflict, retain the current
plan and all schema-consumer repairs in the cumulative result; repairing the
superseded intermediate branch is unnecessary.

Record known ancestor findings against the final code once:
#309 schema consumers -> #361 plus original-head repair `b628e6aaa`;
#310 reaper race -> #317; #311 queued reset SQL -> later synchronous repair;
#313 staff mapping/clocks -> #363; #339/#352 recovery/maintenance paths -> #362.
Confirm those fixes are in the candidate. Resolve/disposition the findings with
their existing proof; do not manufacture new repairs for obsolete heads.
#330 and #337 are handled below; DurisWeb #97 has the two existing probe fixes.
Complete applicable review of the cumulative candidate, without waiting for CI.
Superseded PR closure and final merging belong to a later authorized integration
step; this plan edit performs neither.

### 2. Close only the known qualification gaps

- **Drop the privileged systemd helper project.** Remove the root-required
  `--systemd` qualification mode and its instructions from the final candidate,
  along with its now-unused unit-management code. Keep the direct launcher
  qualifier unprivileged and remove its forced Git safe-directory bypass.
  Never instruct root to execute a user-writable checkout: an in-script UID
  refusal alone is not a security boundary. This removes #330's dangerous
  workflow without a replacement privileged API, installation, sudo policy,
  registration system or another systemd wipe run. Preserve the unpublished
  helper draft in its paused worktree; do not import or develop it.
- **Fix #337's existing restore assertion.** Immediately after the first restored
  boot, require recovery of the frozen Redis generation in that boot's own log
  window, before gameplay or another boot can hide a failure. Wait for the
  resulting fresh checkpoint and check second-boot recovery separately. Reuse
  the existing sequence/checkpoint logic. No restore framework or extra modes.
- **Keep the two already-written DurisWeb probe fixes:** literal loopback
  principal matching and bounded durable outbox-ACK polling. Preserve their
  focused proof; if the temporary executable check is gone, add/recreate only
  those cases in the existing test arrangement. No new website feature and no
  repeat full website wipe for these probe-only changes.
- Update only the affected runbook/regression guidance: supervised direct
  operation, external-writer stop/start, removed root qualifier, truthful restore
  assertions and coverage limits. Reuse the existing telemetry and donation
  cutover instructions.

### 3. Prove the remaining path once and close the evidence

First check syntax, report-path writability and the small changed probe/refusal
cases. Keep existing root-owned/historical reports intact; use owned output in
the final candidate checkout. Do not burn a five-minute run on a known setup error.

Run the existing direct-launcher matched-restore journey as the ordinary user,
using the verified existing binary:

```text
python3 tests/async/run_pwipe_runtime_journey.py --redis --restore <verified-existing-production-binary>
```

This is one planned real countdown covering the latest wipe, fresh gameplay,
save/reconnect/reboot and the repaired matched SQL/filesystem/Redis restore.
Use its existing disposable database/environment. Do not add a second database
engine run, another systemd run or another standalone happy-path run. The current
CLI excludes combining restore with website/systemd; do not redesign it to combine
modes. Repeat only if this run fails or a subsequent relevant change invalidates it.

Reuse the completed native matrices and builds. Run required checks only for
changed files; C/C++ changes, if genuinely required, still require `make -C src`,
changed-line formatting and their affected executable regression. No global
regression sweep, clean-build cycle or CI waiting phase.

Finish with four short evidence dispositions in this plan, using existing records:

1. Reset/preservation contract and supervised operator runbook match the candidate.
2. Actual reset-to-fresh-gameplay proof identifies the revision, binary, command
   and passing assertions.
3. Existing failure/fence/retry proof plus the corrected first-boot restore prove
   the supported recovery procedure.
4. Known findings are fixed, disproven, removed with their unsupported workflow,
   or explicitly outside the narrowed scope; no blocker of the supported wipe
   remains. The existing lifecycle inventory gets a delta check for candidate
   changes, not a fresh repository-wide consumer audit.

Record the reduced scope in #264/#97's readiness description when later authorized
to publish completion. Claim only the supervised configuration qualified here.
A production wipe/deployment still needs its own authorization. Once these four
items and required review hold, the technical qualification is done: no further
hardening phase, extra PRs or optional work.

## Preserve the stopped work

Do not switch/reset/clean the primary checkout (`branch/contain-learning-feedback`).

Server drafts: `/home/aiwithapex/projects/duris-issue264-plan`, branch
`branch/issue-264-unprivileged-qualifier`, based on `10acd1176`. Dirty files:
`docs/ongoing-projects/plan.md`, `docs/testing/REGRESSIONS.md`,
`tests/async/run_pwipe_runtime_journey.py`, and untracked
`tests/async/pwipe_systemd_helper.py` / `test_pwipe_systemd_helper.py`.
Preserve them; selectively carry only the changes retained above.

Website drafts: `/home/aiwithapex/projects/durisweb-issue264-presence`, branch
`branch/issue-264-website-runtime-journey`. Dirty files:
`backend/src/test/pwipeWebsiteProbe.ts` and `docs/development.md`.
Recorded format/lint/types/build, two suites/nine tests, and compiled
selector/delayed-ACK/timeout checks passed; full joint rerun was not performed.
Temporary evidence: `/tmp/issue264-web-probe-{format,lint,type,build,tests,review}.log`
and `/tmp/issue264-web-probe-review.mjs`; use it only if still available and valid.

## Ablation result

Removed the seven-phase restart and stale estimates; new privileged-helper work;
repeat systemd/website/engine matrices; blanket inventory re-audits; per-ancestor
repair/merge/review loops; new PRs; duplicate history; and unrelated follow-ups.
Retained the small restore fix because the current assertion can report success
after a failed first restore. There is no new ETA or speculative work allowance.
