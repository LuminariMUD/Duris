---
name: help-update
description: >-
  Process Duris missing-help requests in lib/etc/help and website Help Suggestions.
  Review submitted new pages and edits, publish verified help, and retire processed
  requests through file cleanup or recorded review decisions. Use standalone or
  during deployment preparation.
---

# Help Update

Process bounded batches from both the missing-help log and the website submission
queue unless the user explicitly limits the input. Paths are relative to the MUD
repository root. Read `AGENTS.md` and preserve existing source edits. Honor
draft/review-only requests; editing this skill does not process live feedback.

Confirm the intended runtime directory and `.env` environment/database target
without exposing credentials. `ENVIRONMENT=production` means production even on
localhost or under a directory named `staging`; importer `--local` selects the
configured database, not a development database. Reuse authorization from an
explicit [deployment](../deploy-production/SKILL.md) or help-publication request.
Normal execution includes website review decisions and their built-in submitter
notifications. Confirm the website target and staff access as described below.
If production permission is missing, finish the source changes and preview, then
request approval for publication, website reviews, and log cleanup on that target.

For `lib/etc/help`, read the shared
[feedback file procedure](../references/player-feedback.md) and snapshot original
bytes and occurrences before investigation. For website submissions, follow
[Help Suggestions](references/website-suggestions.md) to capture and review the
queue before any bulk help import. An empty log does not skip the website queue.
Deduplicate topics across both inputs while retaining a disposition for each log
occurrence and suggestion ID. During deployment, use its recovery directory;
finish publication and lookup verification before `$news-update`, and leave
cleanup prepared for the existing restart boundary. Standalone use does not
require invoking deployment or processing bugs/news.

## Resolve the missing topics

Investigate every captured query against maintained help sources, the live
catalog, command aliases, and the owning code/configuration. Normalize case and
surrounding whitespace for grouping only. A logged miss means zero search
results, not merely a missing exact title. Typos, nonsense, already-covered
topics, and temporarily stale catalogs do not automatically need new pages.

Trace plausible named abilities, items, and mechanics before deciding a query
is unclear. Do not reject a meaningful gap because its implementation takes work
to find. If focused research cannot identify an actionable topic, record why it
is unclear and reject it for cleanup. Do not invent documentation or leave
unfinished research as a final disposition.

For meaningful gaps, add a useful topic or alias in the maintained source,
following [HELP_STYLE_GUIDE.md](../../../docs/content/HELP_STYLE_GUIDE.md) and
[HELP_SYSTEM.md](../../../docs/content/HELP_SYSTEM.md). Explain verified syntax,
eligibility, costs, limits, and examples. Check both `help/duris_help_parsed.hlp`
and `lib/information/help_index`: parsed help wins duplicate titles, and individual
`lib/information/` pages have their own ownership. Website approval writes the
database, so reconcile accepted content into maintained sources using the website
procedure; do not leave accepted help only in the database. Do not create one
page per spelling. Run the innate generator only when its content actually needs
updating. When deployment calls this skill, also update help
affected by the pulled release.

## Publish and verify

Follow the website procedure's approval/import ordering before live writes.
For source changes, review the diff, run `git diff --check` on changed help paths,
and run `python3 scripts/format_help_topics.py`; if using `--write`, retain only relevant
changes. Preview with `./scripts/import_help_to_prod.sh --local --dry-run` and
inspect parser output, title collisions, and the destination. The bulk importer
also publishes information files including news: review that scope and preserve
intentional live content before importing. Dry-run does not back up or compare
the database.

Before an authorized source-help import, take a database backup with
`scripts/backup_pfiles.sh`, or reuse the deployment's applicable verified backup.
Keep recovery files outside `bin/`. Publish using
`./scripts/import_help_to_prod.sh --local` and its normal confirmation. Website
approvals publish through their review workflow and do not require a second bulk
import solely for publication. Do not use `--news-only` for help or `--clean`.
Inspect the changed stored entries; stop on import errors and inspect their
effects before retrying.

Log into the intended game with the configured account, refresh with `page help`,
confirm catalog publication using `page help status`, and run the actual
`help <original query>` lookups and accepted website titles/aliases. Verify the
intended new or aliased text, not just command-attribute output or a database row.
Verify existing coverage too before marking a query already handled. Restore
changed verification preferences, then
quit and close the session unless deployment still needs that connection.

Failed imports, refreshes, or lookups leave affected entries blocked. Resolve
them while the game stays online; do not announce unverified help as completed.
Retain the authored source changes, including `lib/information/help_index`, for
review or the deployment's final commit.

## Clear processed requests and report

For the log, record each occurrence as published and verified, verified already
covered, or rejected with a reason. Use the shared
[cleanup procedure](../references/player-feedback.md#clear-processed-feedback)
to remove those entries, including rejected unclear queries. Preserve new
arrivals and entries blocked by a concrete failed operation. Clear the file
completely when the captured batch is resolved and no new requests remain.
Report publication/lookup and cleanup results separately; pending cleanup is
unfinished work, even when help publication succeeded.

Website suggestions are retired through recorded review statuses, not deletion
or file truncation. Report their IDs and approved/rejected/revision-requested/
blocked counts separately; retain review history and unchanged submissions awaiting
their author. A verified revision request completes that review, not publication.

Report changed source files, topics and lookup commands, evidence for each
disposition, log processed/rejected/new/blocked counts, and concrete failures.
A standalone run does not restart the game, author news, or commit/push.

When called by deployment, return the verified source diff, topic list, useful
lookup commands, publication evidence, website review outcomes, and log cleanup
record. `$news-update` uses the verified additions as a separate content source,
not as merged GitHub history. Deployment coordinates cleanup at its restart boundary
and then
[commits/pushes the verified changes](../deploy-production/SKILL.md#6-commit-and-push-verified-content-and-feedback-directly-to-master).
