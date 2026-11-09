---
name: bug-triage
description: >-
  Investigate Duris bugs, ideas, and typos in lib/reports against current master,
  existing GitHub issues, and open PRs. Consolidate actionable untracked work into
  few issues and safely clear processed reports, standalone or before deployment.
---

# Bug Triage

Process a bounded batch of player bugs, ideas, and typos. Paths are relative to the
repository root. Read `AGENTS.md` and confirm the intended runtime directory and
`.env` environment without exposing credentials. Honor review-only requests.
Editing this skill does not process reports or create issues.

A request to run this workflow authorizes necessary GitHub issue creation and
processed-report cleanup on the specified target. Reuse authorization from an
explicit [deployment](../deploy-production/SKILL.md); do not ask again for its
issue filing or cleanup. Resolve an unknown/mismatched target before mutations.
This scope does not include unrelated bug fixes, issue closures, comments on
existing discussions, announcements, a restart, or commit/push.

Read the shared [feedback file procedure](../references/player-feedback.md).
Snapshot `lib/reports/bugs`, `lib/reports/ideas`, and `lib/reports/typos` as one
bounded batch, preserving each file's record format, bytes, and occurrences.
Keep the source file and occurrence mapping in the private disposition record.
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

For every report, trace the relevant command and code/data/content path to
distinguish a defect, enhancement request, or text error from user error or an
unclear claim. Evaluate ideas as enhancement/design requests and typos as content
corrections; neither needs a code defect to be actionable. Intended behavior alone
does not invalidate a proposal to change it. Use source and existing evidence;
do not provoke destructive gameplay or run a broad test campaign on production.
Compare the running revision, deployment's pulled SHA when applicable, and pinned
master. A fix on master may not yet be live or in the release being deployed;
record that distinction.

An actionable symptom can lack a confirmed reproduction or root cause. Track
such defects with the known facts and uncertainties; do not require a completed
fix before filing. A concrete idea or source-backed interaction needing a design
decision can be tracked with that decision explicit. Reject claims too vague to
support a useful issue only after focused research, recording the missing facts.

## Check existing work before filing

Search the identified repository's open and closed issues and PR history using
symptoms, commands, entities, and likely root causes. Prefer the GitHub connector;
use paginated GitHub API/`gh` reads if it cannot provide adequate coverage. Inspect
candidate bodies (including checklist items in consolidated issues), discussion,
patches, and merge state, not just similar titles. Check all relevant result pages
before concluding that no issue or open PR exists. A failed or incomplete search
is not evidence of absence.

Give every original occurrence a disposition:

- **Resolved on current master:** identify the covering commit/PR and verify the
  fix, implemented idea, or corrected text in the pinned tree. A merged PR or
  closed issue alone is insufficient. Investigate a recurrence after the fix
  rather than automatically dismissing it.
- **Already tracked:** link the existing issue (open or closed) or open PR that
  covers the actual work. Do not create a duplicate. Record its current state;
  a closed issue is not proof of a fix, and an open PR is not shipped behavior.
  A closed, unmerged PR alone does not resolve or actively track the work.
- **Actionable and untracked:** only when there is no verified solution on current
  master, no existing issue covering the work, and no covering open PR, include
  it in the consolidated issue plan below. An unimplemented idea may be tracked
  for a maintainer decision without claiming it is an accepted feature or defect.
- **Invalid or unactionable:** record the source-backed reason no action is needed
  or why focused investigation could not establish an actionable report. Reject
  it for cleanup; do not create speculative empty issues merely to empty the files.

## Batch GitHub issue creation

Group duplicates across all three files and plan the entire batch before writing
to GitHub. Default to one consolidated checklist issue for actionable untracked
work, with sections by subsystem or theme. Combine related distinct defects,
ideas, and typos instead of automatically allocating a separate issue to each
report, occurrence, or distinct defect. Split only when independent priority,
ownership, or an urgent defect makes joint tracking impractical, and keep the
total small.

Keep each distinct task identifiable with its own checklist item and evidence:
expected/actual behavior and available reproduction steps for bugs, requested
behavior and open design decisions for ideas, or affected text/location and
proposed correction for typos. Include relevant commands or vnums, source evidence, checked SHA,
confirmed versus unverified facts, and related history. Keep raw player records
and identities private. Map every original occurrence to its covering issue/item
in the private disposition record. Verify the returned issue URL and contents
cover all mapped items before marking those reports processed.

Recheck master and relevant issue/PR results before creation; inspect any newly
landed changes. If master moves during the batch, review the additional range for
affected decisions before claiming completion.

Create issues sequentially with pauses between writes; do not issue parallel
creates or burst through individual reports. On a rate-limit, abuse, or spam
warning, stop further GitHub writes for that run, honor any retry guidance, and
retain affected reports and the disposition record for a later run.

If lookup or creation fails, inspect the failure and retain affected actionable
reports until it is resolved. An unknown create outcome requires checking whether
the issue already exists before retrying. A draft is not a filed issue. Report
the exact failed action; do not relabel an external failure as an invalid report.
Deployment must resolve these preparation failures before its routine cutover.

## Clear processed reports and report

Use the shared
[cleanup procedure](../references/player-feedback.md#clear-processed-feedback)
to remove reports verified resolved, already tracked, successfully filed, or
rejected, including unclear reports rejected after investigation. Preserve new
arrivals and reports blocked by concrete failed operations. Clear each file
completely when its captured batch is resolved and no new reports remain.

Report the checked master SHA, disposition reasons, fixed commits, existing/new
issue or PR links, per-file processed/rejected/new/blocked counts, total new issue
count and grouping rationale, and each file's verified cleanup or precise pending
action. Triage and issue creation do not belong in player news. During deployment,
return the disposition and cleanup record to its restart coordination and
[final commit/push step](../deploy-production/SKILL.md#6-commit-and-push-verified-content-and-feedback-directly-to-master).
