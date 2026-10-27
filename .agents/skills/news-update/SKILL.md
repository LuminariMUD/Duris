---
name: news-update
description: >-
  Update Duris player news from GitHub history and publish it to the current environment.
  Use when asked to update news, catch up missing announcements, or turn landed
  changes into comprehensive, entertaining, nontechnical player news with the
  file's established MUD colors and layout.
---

# News Update

Update `lib/information/news` itself unless the user requests a draft or review only.
Give returning players the whole useful story: what changed, who it affects, how
to use it, and any costs, limits or catches. Comprehensive means every distinct
player-facing change is accounted for, not one bullet per commit. Make it a good
read without sacrificing facts or hiding less glamorous fixes.

Paths below are relative to the repository root. Read the checkout's `AGENTS.md`
and preserve existing worktree edits.

Run this skill in the environment that should receive the news. Check `.env`'s
`ENVIRONMENT` and the effective database host/port/socket/name without exposing
credentials. Treat `ENVIRONMENT=production` as production even on localhost or
under a directory named `staging`; `--local` does not select a development database.
Verify the destination before writing. An unknown or mismatched target must be
resolved before publication, while independent news preparation can continue.

## Establish what is actually missing

Read the current news, especially the introduction, newest dated sections and
the boundary of the historical archive. Use the recent sections as the style
model; the older archive is a historical record, not a template for new jargon
or formatting. Determine the current source repository and intended branch from
Git remotes and GitHub metadata rather than hardcoding an owner or branch.

Identify the last **substantive coverage update**, not merely the last edit:

```sh
git status --short
git remote -v
git log --follow --format='%H %aI %cI %s' -- lib/information/news
```

Inspect the relevant news diffs and compare the announced features with their
source history. A corrected link, new title or color pass does not advance the
coverage boundary. An `Updated:` date is a clue, not proof that every earlier
change was covered. Recheck the newest already-covered period for omissions and
same-day changes. If no reliable boundary exists, widen the review to the earliest
unverified period; do not invent a clean starting point to shorten the task.

Verify the current GitHub tip and record its full SHA. Default to landed history
on the repository's default branch unless the user names another release/branch.
Use the GitHub connector for repository and PR context when available. For a
complete history inventory, fetch the appropriate remote branch without changing
the checkout, or use paginated GitHub API/`gh` reads. Capped search results are
discovery aids, not evidence that the whole range was reviewed. If a connector
cannot enumerate the range, use Git or a paginated API for that part.

Use ancestry between a verified coverage baseline and the pinned tip. Review
direct commits and all merged branch changes, including squash merges; do not
rely only on PR titles, `--first-parent`, a date filter, or the most recent N
commits. Old author dates can arrive in new merges. Check the inventory total
against `git rev-list --count BASE_SHA..TIP_SHA` (substitute the verified SHAs),
and account separately for the overlap reviewed before that baseline. Compare the
pinned tree with the local checkout and inspect `git show SHA:path` when they
differ, so unpublished local work cannot slip into announcements. If remote access
fails, continue useful local research but report the exact verified boundary.
Do not claim GitHub is fully covered or substitute an unverified local HEAD.

When an authorized deployment supplies newly authored and published help, include
those specific additions as a separate content source alongside the GitHub history
inventory. Verify their source diff and successful in-game lookup, and announce
the useful topics/commands without calling local edits merged history. Keep the
GitHub baseline/tip accounting unchanged. This exception does not include other
unpublished local work or bug-report triage and issue creation.

## Account for the whole range

Keep a working inventory keyed by commit SHA or PR, with the source, each distinct
change, its player impact, and its disposition. A grouped PR entry must list its
member SHAs so the inventory still accounts for every commit:

- Included: map it to a new or corrected news bullet.
- Already covered: identify the existing news section/bullet.
- Superseded or reverted: identify the later change and surviving behavior.
- No player effect: give a concrete reason, such as tests alone or moving code
  without changing behavior.
- Unresolved: name the missing evidence and investigate it before claiming completion.

Large histories can be reviewed in batches, but every inventory entry needs a
disposition. Inspect changed paths and patches, not just subjects. A maintenance
commit can fix lost items; a grand feature title can contain only groundwork.
Inspect merge resolutions for behavior not present in the branch commits and
deduplicate the merge and its component changes. One commit can contain several
independent changes; accounting for one does not account for all of them.

Trace important claims to the code, help, settings or world data at the pinned
tip. Use PR descriptions and discussion to explain intent, then resolve conflicts
against the landed implementation. Read follow-up fixes and reversions together.
Do not announce an undone feature, a proposed issue, an open PR, a disabled feature
as available, or a test fixture as a game rule. Explain a changed current rule
when older news would otherwise mislead players. Preserve dated history; correct
an actual factual mistake with evidence instead of silently rewriting past rules.

Sweep across the full changed-file inventory: combat; races/classes and character
creation; spells/skills/innates; gear and crafting; loot, money and storage; pets
and groups; quests, achievements and rewards; zones, travel and ships; kingdoms
and guilds; login, accounts, clients, displays and help. These are review prompts,
not mandatory headings. Include bugs and restrictions as well as new features.
Technical work belongs in news only when it has a supported player consequence.
Translate a concrete crash or lost-progress fix into that consequence; do not
turn a refactor or new test into a promise of faster or safer play.

Write release news in its final player-facing form. Keep deployment, publication
and reboot status in the operator report, never in the news file; deployment must
not require a second edit to remove temporary status notices. Do not infer
activation from a merged commit when reporting deployment status.

## Write for the adventurer, not the developer

Use a welcoming, knowledgeable voice, speaking directly to `you` and `your`
character. A lively heading or a little in-world humor can make a section inviting:
"Your backpack can breathe again" works only when the following facts explain
the actual bag change. Keep jokes brief, use exclamation marks sparingly, and
describe losses or balance reductions plainly. Avoid hype such as "lag-free",
"never lose an item again", or "everything is fixed" without evidence.

Lead each bullet with the practical change. Follow with affected characters,
conditions and a usable command when relevant. Keep sentences short, usually
one change per bullet. Split complicated systems into a few related bullets
rather than hiding their rules in a giant paragraph. Group repeated fixes by
the experience they repair, but preserve distinct consequences and exceptions.
There is no arbitrary bullet limit: tighten wording before dropping coverage.

Keep precise details that help a player decide or act: eligibility, level, target,
cost, currency, waiting time, duration, number of uses, restrictions and commands.
Verify numbers and units; a code pulse or tick is not automatically a second or
combat round. Preserve command spelling, argument order and optional arguments.
Explain unfamiliar game terms on first use when needed. Replace engineering terms
such as transaction, persistence, async, cache, race condition, migration, mutex,
schema and idempotency with the behavior the player notices. Avoid source paths,
function names, SHAs, issue numbers, tests and implementation narratives in the news.

For example, given verified source behavior:

- "Serialize coin mutation with durable ownership" becomes "Picking up coins
  no longer leaves your purse showing the wrong amount."
- "Preserve nested inventory across recovery" becomes "Your bags keep the bags
  inside them, and their contents, when the game restarts."
- A new combat ability needs its eligible race/class, usable targets, restrictions
  and command, not just "New ability added!"

These examples illustrate translation, not features to announce without evidence.
Read the draft as someone who has never programmed: every bullet must still make
sense, and a curious player should know what to try or what to expect.

## Keep the Duris look

Use plain text containing the game's literal color tokens, not Markdown rendering,
HTML, terminal escape bytes, emoji or a code block in the news file. The recent
news provides this palette:

| Token | Use |
| --- | --- |
| `&+W` | Banner rules, `Updated:` line, occasional important limitation |
| `&+Y` | Main title, headline, bullet marker, meaningful numbers and costs |
| `&+R` | Date or date range; sparing emphasis on danger |
| `&+C` | Topic headings, quoted commands and useful links |
| `&+G` | Occasional positive milestone or completion |
| `&+M` | Occasional distinctive item or feature name |
| `&+L` | Muted separator or an existing name's coloring |
| `&n` | Reset to normal text after a colored span |

Favor the current rich style: `&+Y-&n` bullets, two-space continuation indentation,
blank lines between topics, and mostly uncolored body text. Preserve canonical
multicolor place/item names when useful; do not color every word. Use `&n`
consistently in new text even though the renderer also accepts `&N`. Finish
headings and highlighted spans with a reset. If a colored phrase wraps, reset
before the newline and reapply on the next line; the renderer resets at newlines.

Keep the centered `DURIS PLAYER NEWS` banner with 70-character `=` rules and the
70-character `-` section rules. Wrap new prose to roughly 70-76 visible columns,
at most 78 where practical, counting color tokens as zero width. Shorten or wrap
headlines too. Never split a color token; keep command syntax together where it
fits. Read a color-stripped preview as well as the source to catch awkward wraps.

Use this shape, adapting dates, headline and topics to the evidence:

```text
&+W======================================================================&n
&+Y                           DURIS PLAYER NEWS&n
&+W======================================================================&n
&+WUpdated: Month DD, YYYY&n

Welcome back! [Brief, accurate summary of the period and its highlights.]
The newest changes come first. Later updates replace older rules.

&+RMM/DD/YY - MM/DD/YY&n &+L-&n &+YShort, inviting headline&n
&+W----------------------------------------------------------------------&n

&+CA topic players recognize&n
&+Y-&n [Practical change, with &+C'command'&n or &+Yvalue&n when useful.]
  [A condition or consequence that the player needs to understand.]
```

Place new material after the introduction and before the previous newest section.
Give a later release on the same day its own top block; do not append it beneath
an older, unrelated headline. The newest headline and main player-facing addition
must appear on the first page at the game's default screen height. Shorten the
introduction if needed, and check the color-stripped first-page preview.
Use newest-first date blocks; split a long catch-up into useful weekly or monthly
sections rather than one enormous update. Group by player topic within each block.
Update the `Updated:` line and introductory coverage range to match what was
actually reviewed. Use verified landing dates for chronology, not a misleading
author timestamp; resolve timezone/future-date anomalies before dating a section.
Preserve existing sections and the `EARLIER NEWS` archive unless a specific
correction is needed. On a repeat run, reconcile with the existing bullets and
avoid duplicate announcements or changing dates when no news changed.

## Verify and finish

Before calling the file fully up to date:

- Reconcile every inventory entry with the final draft. Every included claim has
  source evidence, every omitted change has a reason, and no unresolved player
  change is hidden by a broad "stability improvements" bullet.
- Check both directions: history to news for omissions, and news to current
  implementation for invented details, stale values, reversions or overclaims.
- Recheck the remote tip. If it moved, review the additional range; otherwise
  report the pinned SHA as the verified cutoff. If a moving branch or unavailable
  source prevents a complete audit, report the precise outstanding range.
- Read the full new text for tone, practical detail and nontechnical clarity.
  Inspect visible widths, complete/reset color tokens, date order, blank lines,
  final newline and the diff. Keep unrelated edits and the archive intact.
- Run `git diff --check -- lib/information/news` and
  `bash -n scripts/import_help_to_prod.sh`, then always run
  `./scripts/import_help_to_prod.sh --news-only --dry-run` before publication in
  any environment. Check the destination, nonempty source and news-only scope.
  Dry-run does not compare database content, create a backup or prove publication.
  If configuration is missing, report the limitation without changing `.env`.

Report the changed file, covered period and source baseline/tip, important source
links, the review/preview results, and any remaining gaps. Keep the coverage notes
and technical evidence out of the player news. Do not create an extra committed
changelog or tracking framework just to run this workflow.

A normal update includes publishing to the verified current environment with
`./scripts/import_help_to_prod.sh --news-only`; honor explicit draft/review-only
requests. Use the production owner/user permission required by `AGENTS.md`, reusing
authorization already given. If permission is missing, prepare the complete news,
preview and recovery copy first, then request approval for that specific target.

Before the live import, preserve the existing database news row in a protected,
uncommitted recovery copy and double-check the reviewed diff and target. Use only
`--news-only`, never the bulk mode or `--clean`. After success, verify stored news
byte-for-byte against the file and reload cached news with plain `page` (no
arguments). If a separately authorized deployment already includes a reboot,
perform the readback after that reboot instead of reloading beforehand.

Log in and run the actual `news` command. Confirm that its first page shows the
newest headline and main addition, then use the pager to read through the entire
new section. Enable paging if needed and restore any preferences changed for
verification. A matching database row, website API response or help lookup alone
does not prove players see the update. If reload or player-visible readback cannot
be completed, report publication and verification separately with the missing
check; do not claim the update is fully verified. Quit and close the session.

Stop on errors and inspect the result before retrying. Do not restart the game,
change unrelated data, or send announcements as part of this workflow. A standalone
news update does not commit/push. When invoked by an authorized
[deployment](../deploy-production/SKILL.md#6-commit-and-push-the-verified-news-directly-to-master),
return to its final step to commit the verified news file and push it directly to
`master` after deployment verification.
Details are in `docs/content/HELP_SYSTEM.md`, under "Publishing news only".
