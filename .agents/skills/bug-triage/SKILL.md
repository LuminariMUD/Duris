---
name: bug-triage
description: >-
  Investigate Duris reports in lib/reports/bugs against current master and existing
  GitHub issues and open PRs, file valid untracked defects, and safely clear
  processed or invalid reports. Use standalone or during deployment preparation.
---

# Bug Triage

Process a bounded batch of player bug reports. Paths are relative to the repository
root. Read `AGENTS.md` and confirm the intended runtime directory and `.env`
environment without exposing credentials. Honor review-only requests. Editing
this skill does not process reports or create issues.

A request to run this workflow authorizes necessary GitHub issue creation and
processed-report cleanup on the specified target. Reuse authorization from an
explicit [deployment](../deploy-production/SKILL.md); do not ask again for its
issue filing or cleanup. Resolve an unknown/mismatched target before mutations.
This scope does not include unrelated bug fixes, issue closures, comments on
existing discussions, announcements, a restart, or commit/push.

Read the shared [feedback file procedure](../references/player-feedback.md).
Snapshot only `lib/reports/bugs`, preserving multiline records and occurrences.
During deployment, use its recovery directory and captured batch; finish triage
and issue creation before announcing the restart, with cleanup prepared for that
boundary. Standalone triage does not require deployment, help work, or news.

## Establish current master and investigate

Identify the repository from Git remotes/GitHub metadata. Fetch its current
`master` and record the full SHA without switching branches or pulling code into
the running checkout; for an `origin` remote, use `git fetch origin master` and
pin the fetched revision. Inspect that tree with `git show`/`git log` or GitHub
reads when the local checkout differs. Do not substitute a stale local `master`,
the running binary, or an open PR for current master. If remote access fails,
continue local research but keep decisions depending on that check unresolved.

For every report, trace the relevant command and code/data path to distinguish
a defect from intended behavior, user error, or an unclear claim. Use source and
existing evidence; do not provoke destructive gameplay or run a broad test
campaign on production. Compare the running revision, deployment's pulled SHA
when applicable, and pinned master. A fix on master may not yet be live or in
the release being deployed; record that distinction.

An actionable symptom can lack a confirmed reproduction or root cause. Track
such defects with the known facts and uncertainties; do not require a completed
fix before filing. A source-backed interaction needing a design decision can
be tracked with that decision explicit. Reject claims too vague to support a
useful issue only after focused research, recording the missing facts.

## Check existing work before filing

Search the identified repository's open and closed issues and PR history using
symptoms, commands, entities, and likely root causes. Prefer the GitHub connector;
use paginated GitHub API/`gh` reads if it cannot provide adequate coverage. Inspect
candidate bodies, discussion, patches, and merge state, not just similar titles.
Check all relevant result pages before concluding that no issue or open PR exists.
A failed or incomplete search is not evidence of absence.

Give every original occurrence a disposition:

- **Fixed on current master:** identify the covering commit/PR and verify the
  fix in the pinned tree. A merged PR or closed issue alone is insufficient.
  Investigate a recurrence after the fix rather than automatically dismissing it.
- **Already tracked:** link the existing issue (open or closed) or open PR that
  covers the actual defect. Do not create a duplicate. Record its current state;
  a closed issue is not proof of a fix, and an open PR is not shipped behavior.
  A closed, unmerged PR alone does not resolve or actively track the defect.
- **Valid and untracked:** only when there is no verified solution on current
  master, no existing issue covering the defect, and no covering open PR, create
  one GitHub issue per distinct defect. Include expected/actual behavior,
  relevant commands or vnums, source evidence and checked SHA, known reproduction
  steps, and confirmed versus unverified facts. Link related history. Keep raw
  player records and identities private. Verify the returned issue URL and
  contents before marking it processed.
- **Invalid or unactionable:** record the source-backed non-bug reason or why
  focused investigation could not establish an actionable report. Reject it for
  cleanup; do not create speculative empty issues merely to empty the file.

Group duplicate symptoms for investigation and issue filing while accounting for
every original occurrence. Recheck master and relevant issue/PR results before
creation; inspect any newly landed changes. If master moves during the batch,
review the additional range for affected decisions before claiming completion.

If lookup or creation fails, inspect the failure and retain affected actionable
reports until it is resolved. An unknown create outcome requires checking whether
the issue already exists before retrying. A draft is not a filed issue. Report
the exact failed action; do not relabel an external failure as an invalid report.
Deployment must resolve these preparation failures before its routine cutover.

## Clear processed reports and report

Use the shared
[cleanup procedure](../references/player-feedback.md#clear-processed-feedback)
to remove reports verified fixed, already tracked, successfully filed, or
rejected, including unclear reports rejected after investigation. Preserve new
arrivals and reports blocked by concrete failed operations. Clear the file
completely when the captured batch is resolved and no new reports remain.

Report the checked master SHA, disposition reasons, fixed commits, existing/new
issue or PR links, processed/rejected/new/blocked counts, and verified cleanup
or the precise pending action. Triage and issue creation do not belong in player
news. During deployment, return the disposition and cleanup record to its restart
coordination and [final commit/push step](../deploy-production/SKILL.md#6-commit-and-push-verified-content-and-feedback-directly-to-master).
