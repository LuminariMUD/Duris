# Help system improvement ideas

Date: 2026-11-12
Status: research and proposed ideas; implementation and publication are separate work.

## Does Duris have "Did you mean?"

No, in the inspected checkout. `help` and `info` use the same handler, which
searches help **titles** case-insensitively by substring, retaining `%` and `_`
wildcards. A zero-result search logs the query and returns a missing-topic
message. There is no spelling-distance or phonetic suggestion fallback.
See [`wiki_help()`](../../src/cmd/wikihelp.c),
[`help_title_matches()`](../../src/cmd/help_cache.c), and
[`do_help()`](../../src/cmd/actinf.c).

Luminari-Source does have it. Its current implementation combines bounded
Levenshtein distance with phonetic/prefix/substring candidates, puts close
spellings first, removes duplicate keywords, and limits the combined list to
ten. Suggestions are clickable. A miss says "Did you mean"; a displayed partial
match can be followed by "Perhaps you meant". An exact match stops that fallback.
Sources: [lookup and ranking](https://github.com/LuminariMUD/Luminari-Source/blob/77d9b032db04c6b0e6c80ba32e4178c8a63ecba5/src/core/help.c#L1653-L1842),
[suggestion presentation](https://github.com/LuminariMUD/Luminari-Source/blob/77d9b032db04c6b0e6c80ba32e4178c8a63ecba5/src/core/help.c#L1846-L1900),
and [focused regressions](https://github.com/LuminariMUD/Luminari-Source/blob/77d9b032db04c6b0e6c80ba32e4178c8a63ecba5/unittests/CuTest/test_help_suggestions.c).

## Evidence and boundaries

This is a source study of local checkouts, plus the linked primary web sources:

- Duris `master`: `f8919ad27dd71ddb2e322feb31529c61d84384b7`.
- Sibling Luminari-Source: `77d9b032db04c6b0e6c80ba32e4178c8a63ecba5`.
- Sibling DurisWeb: `37344926c2873ef5afae0093467f054d5573c156`, inspected only
  where its existing help search and suggestion workflow affect these ideas.

No live catalog, production server, private missing-help log, or player data was
examined. Examples below illustrate proposed behavior, unless explicitly marked
as a reproduction. Priorities reflect engineering judgment, not measured player
demand. General help-design proposals are identified separately from features
observed in another MUD. No gameplay code or help content was changed for this study.

## What Duris already has

- A MariaDB-backed catalog refreshed off the game thread, normally every
  60 seconds. Failed refreshes preserve the previous catalog; ordinary reads
  never query MariaDB. Keep this property. See
  [catalog operation and bounds](../operations/help-cache.md).
- Clickable search results and authored `[[topic]]` references, with readable
  text for clients without link support. Pager replay preserves link targets.
  New suggestions can use this existing output path. See
  [help serving and links](../content/HELP_SYSTEM.md#runtime-path-what-players-see).
- Exact-page rendering, redirect support, edit metadata, command-attribute
  footers, and some category-driven generated race/class/spec sections.
- Maintained `class`, `race`, `skills`, and `spells` reference browsers. Help
  should connect players to these rather than recreate their full interfaces.
- Missing-search capture in `lib/etc/help`, an authored `Help` page, and an
  `Index` page with starting points. Improve these rather than invent a second
  missing-topic queue or assume there is no index.
- Content layout and race/class contracts, an import collision report, and
  transactional import checks. A broader help-quality checker should extend
  those checks. See [the content pipeline](../content/HELP_SYSTEM.md).

Two current details affect several proposals:

1. `wiki_help()` collects at most **101** substring matches and only then looks
   for an exact title inside that collection. A later exact title can therefore
   be missed. The collected list has no truncation notice. Its heading calls
   other substring results additional matches; those are not curated related
   topics.
2. `category_id` is partly a **rendering switch**, not just a browsing label.
   Values 25, 9, 16, and 10 trigger different generated sections. The maintained
   importer assigns category 0 to ordinary imported entries; runtime redirects
   require category 1 and a body beginning `Redirect: `. Merely importing that
   sentence as ordinary prose does not create a working redirect.

These follow from [`wiki_help()` / `wiki_help_single()`](../../src/cmd/wikihelp.c)
and [`import_help_to_prod.sh`](../../scripts/import_help_to_prod.sh).

## Useful lessons from Luminari-Source

The following are confirmed in code, rather than inferred from its older system
documentation:

- **Separate good lookup from typo recovery.** Exact keyword and alias matches
  outrank prefix matches. Its suggestion stage adds edit-distance candidates
  before the phonetic fallback. The edit-distance stage retains five candidates;
  the merged list is capped at ten.
- **Aliases participate in lookup and suggestions.** The lookup query combines
  real keywords with tokens from `alternate_keywords`; a real keyword owner
  wins an alias collision. See
  [keyword construction and lookup](https://github.com/LuminariMUD/Luminari-Source/blob/77d9b032db04c6b0e6c80ba32e4178c8a63ecba5/src/core/help.c#L53-L71)
  and [exact-match ordering](https://github.com/LuminariMUD/Luminari-Source/blob/77d9b032db04c6b0e6c80ba32e4178c8a63ecba5/src/core/help.c#L376-L459).
- **Search prose when the title is unknown.** `helpsearch` searches entry text
  and keywords, returns at most 20 entries, and displays clickable titles and
  previews. Despite its name, this is SQL `LIKE` search, not a database FULLTEXT
  index. See [query](https://github.com/LuminariMUD/Luminari-Source/blob/77d9b032db04c6b0e6c80ba32e4178c8a63ecba5/src/core/help.c#L611-L674)
  and [command](https://github.com/LuminariMUD/Luminari-Source/blob/77d9b032db04c6b0e6c80ba32e4178c8a63ecba5/src/core/help.c#L2416-L2498).
- **Audit discoverability.** `helpcheck` checks registered non-social commands
  against one loaded keyword snapshot without issuing player help searches.
  Its current coverage criterion accepts keyword prefixes: useful as a starting
  point, weaker than proving an unambiguous correct destination. See
  [checker](https://github.com/LuminariMUD/Luminari-Source/blob/77d9b032db04c6b0e6c80ba32e4178c8a63ecba5/src/olc/hedit.c#L1518-L1556).
- **Keep mechanics available from their owners.** Its help handlers can dispatch
  to generated feat/class/race and other reference views. Duris already has
  equivalent opportunities through its own reference browsers. See
  [handler registration](https://github.com/LuminariMUD/Luminari-Source/blob/77d9b032db04c6b0e6c80ba32e4178c8a63ecba5/src/core/help.c#L1108-L1135).
- **Treat editing as a publication workflow.** `hedit` supports text, keywords,
  minimum level, database saves, and version-history writes. Version history is
  best effort in the inspected save path, so it is not proof of a complete audit
  trail. See [save implementation](https://github.com/LuminariMUD/Luminari-Source/blob/77d9b032db04c6b0e6c80ba32e4178c8a63ecba5/src/olc/hedit.c#L536-L702).

Borrow those behaviors selectively. Luminari also has synchronous database
lookups, a query-result cache, a handler chain, and file fallback. Duris can add
the useful search behavior to its existing immutable catalog without importing
that architecture or introducing unsupported flat-file runtime persistence.

## Proposed ideas

### 1. Guarantee exact matches before limiting results

Priority: first code change. Scope: small lookup/presentation change.
Origin: direct Duris finding; Luminari's exact-match ordering reinforces it.

Resolve a case-insensitive exact title across the full catalog before limiting
broader results. Then rank other title matches by whole title, word/prefix, and
substring, with deterministic alphabetical ties. Keep authored related reading
separate from "Other title matches". Bound the displayed alternatives and say
when more results exist, with an example of how to narrow the query.

Proof: an exact page still opens with more than 101 alphabetically earlier
substring hits. Cover mixed case, short names, explicit wildcard queries,
zero results, and a full result list. Do not turn an abbreviation with several
plausible matches into an arbitrary first-page selection.

### 2. Add a small, useful "Did you mean?" fallback

Priority: first code change alongside idea 1. Scope: small to medium.
Origin: Luminari behavior, adapted to Duris's cache and link representation.

On a title-search miss, offer up to five close titles, for example
`help firball` suggesting `Fireball`. Require the player to select the suggestion;
do not silently replace the request. Reuse semantic `help <canonical title>`
links, including plain-text fallback, instead of writing raw MXP tags.

Start with bounded, case-insensitive Levenshtein distance over cached titles,
length filtering, early exit, and a fixed maximum suggestion count. As an initial
tuning proposal, allow one edit for three- or four-character words and two for
longer names; suppress fuzzy guesses for one- or two-character queries and for queries
using explicit wildcards. Plain Levenshtein counts a transposition as two edits.
Test that case explicitly rather than promising special transposition handling.

Keep exact and useful ordinary title matches ahead of fuzzy results. For the
first version, show fuzzy results only on a miss. Add Luminari-style suggestions
alongside partial results only if representative searches justify the extra
output. Phonetic matching can follow later if it improves fantasy-name queries;
Luminari's `SOUNDS LIKE` is inspiration, not a reason to add command-time SQL.

Proof: missing/doubled letters, substitutions, transpositions, multiword names,
unrelated gibberish, equal-distance ties, and aliases once idea 3 exists. Measure
the miss path at the existing 20,000-page ceiling. Preserve asynchronous refresh,
the existing input/output bounds, and the temporary-unavailable response.

### 3. Make synonyms and abbreviations resolve to one canonical topic

Priority: early, after defining how aliases survive import. Scope: medium.
Origin: Luminari keywords and Evennia aliases; Duris-specific import constraints.

A player may know an acronym, an old name, or the command rather than the full
topic title. Maintain explicit aliases for those cases. Deduplicate suggestions
and result lists by canonical destination so five synonyms do not consume five
slots. Exact canonical titles should win collisions; conflicting aliases should
be reported for review rather than quietly reassigned.

Do not infer aliases by splitting every title at spaces: multiword titles are
real names. Likewise, a legacy help-index heading containing several words is
not proof that each word currently acts as an independent alias. Normalize
surrounding/repeated spaces deliberately; treat hyphen/space equivalences as a
reviewed compatibility choice where names could collide.

Use the existing redirect capability for a small number of aliases only after
making their category/body shape round-trip through the importer. Add dedicated
alias metadata only if actual content needs exceed that approach. Avoid copied
page bodies and a second independently maintained glossary. Evennia explicitly
supports aliases on help entries. [Source](https://www.evennia.com/docs/latest/Components/Help-System.html)

### 4. Let players search explanations, not only titles

Priority: early. Scope: medium.
Origin: Luminari `helpsearch`; general search-result design.

Add an explicit content-search command, provisionally `helpsearch <words>`.
Review command-prefix collisions before settling its spelling. An explicit
command avoids stealing existing topics named `Search` or treating every
ordinary lookup as a body scan. A miss can point players to this command once
it exists.

Search the published catalog's authored text with title/alias hits ranked first,
then body hits. Show a bounded list of canonical titles and short snippets near
the matching words, with color/markup removed safely. For multiple words, begin
with all words required rather than a large OR search. Explain that generated
live browser details are outside the initial prose search.

Start with a measured bounded scan; if it is too slow at catalog limits, prepare
a compact search index during the existing background refresh and publish it
with the same generation. No new search service or per-query SQL is needed.

### 5. Turn existing starting pages into a practical learning path

Priority: early content improvement. Scope: small content batches.
Origin: Aardwolf browsing patterns plus original Duris task-oriented proposals.

Update the existing `Help`, `Index`, and `Newbie` entry points. The current index
already groups starting topics, so expand and connect it rather than replace it
with an enormous alphabetical dump. Suggested paths include first login and
movement, communication, combat and fleeing, death/corpse recovery, learning
abilities, equipment, travel, and rules. Verify each destination before adding
it, especially where a proposed name is new.

Give each destination a one-line explanation and a clickable reference. Link
to `class`, `race`, `skills`, and `spells` guidance with their actual supported
syntax. Public reference material should remain browsable beyond a character's
current class or level; reading requirements and satisfying them are different.

Aardwolf documents category browsing, prefix indexes with short descriptions,
and updated-help listings. Those are useful interaction ideas; they are not
evidence that Duris lacks an index. [Help overview](https://www.aardwolf.com/wiki/index.php/Help/Help),
[prefix index](https://www.aardwolf.com/wiki/index.php/Help/Index),
[categories](https://aardwolf.com/wiki/index.php/Help/Contents).

Begin with authored hub pages. If automatic categories become worthwhile, keep
browsing metadata distinct from the existing category-driven rendering behavior.
Changing a category must not unexpectedly append racial or specialization facts.

### 6. Make high-use pages answer the practical questions first

Priority: early content improvement. Scope: incremental.
Origin: general help-design synthesis; extends the existing Duris style guide.

Apply the [current authoring guide](../content/HELP_STYLE_GUIDE.md) to small
batches of important pages: purpose, usable syntax, a realistic example,
requirements/targets/costs, common failures, and related reading. For irreversible
or expensive actions, explain the consequence before the example. State units
precisely; a round, tick, pulse, and second are not interchangeable.

Prioritize pages players fail to find or understand, not all old pages by date.
Use concrete questions such as "Why can't I cast this?" to identify missing
explanations and synonyms. These are editorial prompts, not facts about observed
player complaints. Have examples checked against the dispatcher and mechanics.

### 7. Connect authored explanations to the existing live reference browsers

Priority: early links; generated-section changes later. Scope: small to medium.
Origin: Luminari's generated help handlers; Duris's existing reference commands.

Let help explain a mechanic and lead to `class info <name>`, `race info <name>`,
`skills <class or specialization>`, and `spells info <name>` where appropriate.
These commands already own useful current facts; use their actual naming and
eligibility rules rather than create parallel copies inside a new help framework.

Longer term, reduce duplicated progression lists only when imported pages and
generated details have an explicit ownership boundary. Most imported pages are
category 0 today, so a prose edit alone does not make their numbers live. Handle
missing authored text without losing generated facts, following the existing
[class browser](class-command-browser.md). Avoid generating explanations of
balance, item permissions, duration, or stacking from a name or grant table.

### 8. Add a discoverability and link-quality report

Priority: early developer tool. Scope: medium, extending existing checks.
Origin: Luminari `helpcheck`, strengthened for Duris's import semantics.

Build a read-only report from the **effective post-import catalog**, including
the real source precedence, and compare it with registered commands and named
abilities. Report missing destinations, ambiguous aliases, malformed references,
broken redirects/cycles, duplicate titles, and broken `[[topic]]` links. List
legacy `See also` text that needs conversion separately; it is not already a
structured link just because it appears below that heading.

Resolve destinations without invoking ordinary help lookup, which would pollute
missing-search logs. Distinguish an exact or explicit-alias destination from an
incidental substring match; neither structural coverage nor a prefix hit proves
the prose is accurate. Permit deliberate shared pages and disabled-command
explanations. Add failures for newly introduced defects before requiring a
cleanup of every historical finding.

### 9. Use the existing feedback signals to choose the next pages

Priority: early manual review; automation only if useful. Scope: small.
Origin: Duris's existing miss log plus general documentation-maintenance practice.

Group failed searches privately by normalized query and frequency, then classify
them as typo, missing alias, missing page, misleading terminology, or unrelated
input. Repetitions are requests, not unique players. Keep raw text out of Git;
the current records contain arbitrary user input and are best-effort logs.
See [missing-search review](../content/HELP_SYSTEM.md#reviewing-missing-searches).

Connect this review with DurisWeb's existing new/edit suggestion queue. A player
who found a page but still cannot solve the problem needs a way to report that
gap too. Prefer a clear "suggest an improvement" route to the existing workflow
before adding an in-game rating database. Add aggregate suggestion-use metrics
only if a concrete tuning question needs them; a new telemetry system is not a
prerequisite for ideas 1 and 2.

### 10. Reconcile website edits with repository-owned help

Priority: early maintenance correctness. Scope: cross-repository follow-up.
Origin: direct inspection of Duris and DurisWeb write paths.

Duris's content workflow says to edit maintained files and import them. However,
DurisWeb's `reviewSuggestion()` currently applies an approved suggestion directly
to `pages`. A later repository import can overwrite the same title. This is a
source-ownership risk established by the two code paths, not a claim that a
specific accepted edit has already been lost.

Retain the existing website workflow, but make accepted edits round-trip into
the maintained source before the next bulk import, with a conflict check against
the version reviewed. Make review status and successful publication agree on
failure. Prefer a small reviewed export/import reconciliation over a second
editor or full synchronization platform.

Preserve the existing atomic catalog publication and show which source revision
was published. If durable cross-surface links are added, use canonical titles or
an identity that survives import: the current importer deletes and reinserts
rows, so numeric `pages.id` is not inherently a stable help identity.

Source: Duris [`import_help_to_prod.sh`](../../scripts/import_help_to_prod.sh);
DurisWeb [review and application](https://github.com/LuminariMUD/DurisWeb/blob/37344926c2873ef5afae0093467f054d5573c156/backend/src/services/helpSuggestionService.ts#L271-L361).

### 11. Offer concise syntax and contextual explanations where they help

Priority: later, targeted to confusing commands. Scope: small per command.
Origin: Discworld patterns plus original Duris error-message proposals.

Discworld documents `syntax group` and `group help <sub-command>` as shorter
routes into a complex command. [Source](https://discworld.starturtle.net/lpc/playing/documentation.c?path=%2Fconcepts%2Fgroups)
For Duris, pilot concise usage and `help <topic>` pointers on a few commands with
many subcommands, using their current validation path. Do not globally intercept
`<command> help`: some commands accept free text or targets there.

When an action fails, name the actual failed requirement and the relevant help
topic where the command already knows that information. Keep the full article
optional; avoid unsolicited tutorials during combat. Contextual help should
explain known state, not guess hidden mechanics, expose unseen entities, or run
the underlying action as part of a preview.

### 12. Improve long-page navigation, accessibility, and freshness signals

Priority: later presentation work; useful content edits can start earlier.
Origin: Evennia subtopics, Aardwolf updated-help listings, and general help UX.

Split long articles into readable sections with examples and related links.
Evennia supports addressable nested subtopics; borrow the navigability before
adding slash-path syntax. Separate linked pages are enough for an initial Duris
version. [Source](https://www.evennia.com/docs/latest/Components/Help-System.html)

Use short result lists, visible text labels, normal terminal widths, and logical
reading order. Validate generic Telnet, paging on/off, MXP, and structured browser
links. Keep color supplementary and preserve existing replay/chunking behavior.

Separate content review date, import/publication time, and cache generation.
The importer writes `last_update` at import time, so the current outer "Last
Edited" heading alone does not prove recent mechanics review. A modest
recently-changed list should show real content changes, not every reimport;
begin with revision-based editorial notes before adding new schema. Aardwolf's
updated-help listing is a useful precedent, not a substitute for defining those
dates. [Source](https://www.aardwolf.com/wiki/index.php/Help/Help)

## Recommended order and acceptance

1. Deliver exact-match correctness and bounded typo suggestions together.
   Prove ranking, caps, latency, and clickable/plain output with focused tests.
2. Improve the existing help/index/newbie pages and relevant browser links.
   Start the private missing-search review in parallel; it can guide content
   without a new runtime feature.
3. Add alias round-tripping and the effective-catalog quality report. Resolve
   repository/website edit ownership before expanding the authoring workflow.
4. Add explicit prose search with useful snippets. Measure before adding an
   index, and publish any derived data with its catalog generation.
5. Select contextual usage, long-page navigation, and freshness improvements
   according to concrete content or player needs.

For any search change, keep these acceptance requirements:

- Exact titles remain reachable regardless of broad-result caps; ambiguous
  requests expose choices and fuzzy requests never execute gameplay actions.
- Existing `%`/`_` search behavior, redirects, empty default help, `info`,
  attribute footers, and unavailable-catalog responses are deliberately covered.
- Suggestions/results resolve to canonical pages, have deterministic ordering,
  respect output/link bounds, and remain readable without clickable-link support.
- Do not copy Luminari's level filter as a blanket restriction on learning about
  other classes. Duris's current five-field catalog has no per-page access-level
  field or caller-aware lookup. If genuinely restricted help is introduced,
  define one visibility policy for lookup, suggestions, snippets, indexes, and
  website access; a category label or command execution gate is not that policy.
- Test maximum-size miss/content-search paths and refresh failure. No ordinary
  help query should acquire a database connection or add character recovery.
- Content changes preserve source precedence, parser shape, dynamic-section
  ownership, and the transaction/refresh procedure. Publication is verified
  separately from writing a file or accepting a queued refresh request.

Defer a new help service, general provider/plugin framework, external search
engine, embedding store, runtime AI answer generation, wholesale `hedit` port,
and all-at-once content rewrite. None is necessary for the first useful changes.

## Research verification

- Passed `python3 tests/async/test_help_cache.py`: production lookup/render
  bodies and refresh-state regression harnesses.
- Passed `python3 tests/async/test_help_layout.py`: three maintained-content
  layout checks.
- Passed `python3 tests/async/test_help_import_live_parser.py`: importer source
  contracts for title parsing, precedence reporting, and transaction construction.
- A temporary extension of the existing cache harness reproduced both findings:
  `scroe` against a catalog containing `Score` returns the missing-topic response
  without suggestions; an exact `needle` page behind 101 earlier substring hits
  is reachable through `wiki_help_single()` but not through `wiki_help()`.
  These were synthetic catalogs exercising extracted production function bodies,
  not observations of a live player session. The harness extension was not added
  to the repository because this task only records ideas.

Implementation should extend the existing focused tests and use disposable
MariaDB journeys for publication behavior. No build, live import, deployment,
or full production-catalog performance benchmark was needed or performed for
this documentation-only study.
