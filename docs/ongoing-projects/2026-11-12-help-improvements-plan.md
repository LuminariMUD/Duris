# Help improvements implementation plan

Date: 2026-11-12
Status: complete; all implementation and required validation passed. Review-ready stack: #1033 -> #1034 -> #1036. No deployment authorized.
Source baseline: Duris `f8919ad27dd71ddb2e322feb31529c61d84384b7`;
Luminari-Source `77d9b032db04c6b0e6c80ba32e4178c8a63ecba5`.

## Outcome and scope

Implement the five requested improvements, in this order:

1. An exact help title always opens, even when many partial matches exist.
2. A miss can offer a short, clickable "Did you mean?" list.
3. `help`, `help index`, and `help newbie` provide a useful starting path.
4. Important pages explain purpose, syntax, examples, requirements, costs, and
   common failures in practical language.
5. Help directs players to the existing `innate`, `class`, `race`, `skills`,
   and `spells` commands for current reference information.

This is the implementation scope selected from the broader
[ideas document](2026-11-12-help-system-ideas.md). The section numbers here match
the user's five selected outcomes. This plan does not authorize a deployment.

Scope review using the ablation skill: keep the current MariaDB catalog, output
links, pager, authoring formats, and import pipeline. Use a local spelling
comparison and authored navigation. Full-text search, new aliases, automatic
categories, a general help-provider framework, new metrics, website editing
changes, and a general help-quality platform are separate ideas. None is needed
to complete these five improvements. No schema or protocol change is expected.

## Baseline facts (before implementation)

- [`wiki_help()`](../../src/cmd/wikihelp.c) collects up to 101 title matches and
  then searches that subset for an exact title. The cap can hide an exact match.
  Matching is case-insensitive substring search with `%` and `_` wildcards.
  A miss currently logs the query and prints a missing-topic message.
- [`help_cache.c`](../../src/cmd/help_cache.c) supplies an immutable catalog
  loaded off the game thread. The limits include 20,000 pages, 256-byte titles,
  and 32 MiB of source data. Keep help queries free of database operations and
  character recovery delays. See [catalog operation](../operations/help-cache.md).
- `append_help_link()` already produces semantic `help <topic>` links.
  [`valid_output_links()`](../../src/net/output_links.c) currently accepts only
  `help ` command targets. Thus `[[Class]]` opens the Class article;
  `[[class info warrior]]` would search for a help title, not execute that command.
- The importer writes individual information files, then `help_index`, then
  parsed help. Later matching titles win. The effective `Help`, `Index`, and
  `Newbie` pages come from `help/duris_help_parsed.hlp`; editing only
  `lib/information/help` would not update the final Help page.
- `Rules` is supplied by `lib/information/rules`. Do not introduce a duplicate
  Rules article in either later import source. Category 0 is used for ordinary
  imports; changing category values can enable generated content or redirects.
- `innate info <name>` already shows personal access, status, and mechanics
  where a facts provider exists. The current Innate article omits this route.
  Skills and spells information views append authored help; class/race views
  also consume help prose. Keep the useful explanation they depend on.

These facts were checked against the current source and the importer's actual
Python parser functions, without connecting to a database. Topic names below
refer to imported titles, not assumed aliases from words in a legacy heading.

## 1. Make exact searches always work

### Behavior

- Trim surrounding whitespace once for lookup. Whitespace-only input opens the
  default Help page. Preserve multiword spelling and internal spaces; do not add
  automatic hyphen conversions or alias rules in this change.
- Resolve case-insensitive exact-title equality across the complete catalog,
  independently of the partial-result limit. Render the exact article first
  through `wiki_help_single()`, retaining redirect handling and generated sections.
- Preserve ordinary substring/wildcard matching and catalog order for other
  results. A single non-exact match still opens its article; ambiguous matches
  remain a list. No broader relevance-ranking system is needed here.
- Show at most `WIKIHELP_RESULTS_LIMIT` (100) other titles. Track overflow
  separately and display a short "More topics matched; use a longer name"
  message. Never display the extra sentinel as a 101st result.
- When an exact page exists, exclude it from the alternatives. Its article is
  outside the 100-alternative limit. Preserve the distinction between other
  title matches and the article's authored related reading.

### Implementation

Change the selection logic in [`wikihelp.c`](../../src/cmd/wikihelp.c), keeping
one catalog snapshot for the request. A bounded collection for alternatives
must not terminate the scan before exact lookup is complete. Reuse
`help_title_equal()` and `help_title_matches()`; there is no need to change the
database loader, store a second catalog, or change `do_help()`'s delivery path.

Retain the existing attribute footer and the `info`/`rules` command routes.
Normal exact and partial matches must not generate a missing-topic record.
Unavailable catalogs and redirect errors keep their existing responses.

### Proof

Extend [`test_help_cache.py`](../../tests/async/test_help_cache.py) and the real
output harness with an exact page placed after more than 101 alphabetically
earlier substring hits. Verify the article body, exact-first order, exclusion
from alternatives, overflow notice, and the 100-result boundary. Cover zero,
one, 100, and 101 partial matches, mixed case, multiword titles, surrounding
whitespace, empty input, and literal wildcard queries.

The cache test currently substitutes its own substring matcher. Use the
production matcher for wildcard assertions, as the existing output integration
harness does; a simplified test matcher cannot prove wildcard compatibility.

## 2. Add "Did you mean?" suggestions

### Behavior

Only run typo recovery after ordinary title search finds no matches. For example:

```text
> help firball
Sorry, but there are no help topics that match your search.
Did you mean:
  Fireball
```

`Fireball` is an existing semantic link targeting `help Fireball`. Selecting it
follows normal command handling. The miss itself never opens a guessed article
or executes a gameplay action. Plain clients receive the same readable title.

- Return up to five distinct case-insensitive titles, ranked by increasing edit
  distance, then case-insensitive title order, with a stable final tie-break.
- Compare complete titles, including spaces. Use case-insensitive bounded
  Levenshtein distance: one edit for queries of three or four characters, two
  for queries of five or more characters. A transposition counts as two edits.
  This covers `firball` -> `Fireball` and `scroe` -> `Score`.
- Skip fuzzy matching for fewer than three characters, explicit `%`/`_`
  wildcard searches, and queries beyond the existing title-length bound.
  Initial fuzzy comparison follows the current ASCII title-matching scope;
  non-ASCII input/titles continue through ordinary lookup without byte-based
  spelling guesses. Unicode-aware fuzzy search is a separate extension.
- If there are no sufficiently close titles, retain the ordinary miss response.
  Do not pad the list with unrelated topics. Exact/partial results do not gain
  additional fuzzy output in this implementation.
- Log the original missed query once, even if suggestions are displayed.
  Suggestion enumeration and pager replay must not add missing-topic records.
  Do not log default help, cache unavailability, or successful lookups as misses.

### Implementation

Keep the helper and top-five selection local to `wikihelp.c`, unless an actual
second production caller needs an interface. Reuse `append_help_link()` for
each result; do not embed MXP tags or widen command-link permissions.

Use length-difference rejection, bounded working rows, and early exit once the
distance limit cannot be met. Keep only the best five candidates while scanning;
do not sort or copy the entire catalog on each miss. Account for the full
256-byte title bound rather than copying Luminari's 128-character limit.

Measure this path on realistic and worst-case 20,000-title catalogs, including
long common prefixes. If the straightforward distance loop misses the measured
game-loop latency budget, restrict calculation to the distance band before
considering larger machinery. No command-time SQL, phonetic SQL fallback,
query-result cache, service, or configurable scoring system is required.

### Luminari reference points

Use these as behavior and algorithm references, adapting them to Duris's cache
and output ownership:

- [Bounded edit distance](/home/aiwithapex/projects/Luminari-Source/src/core/help.c:1653).
- [Ranking and combining suggestion lists](/home/aiwithapex/projects/Luminari-Source/src/core/help.c:1698).
- [Suggestion lookup and clickable output](/home/aiwithapex/projects/Luminari-Source/src/core/help.c:1834).
- [Suggestion regression cases](/home/aiwithapex/projects/Luminari-Source/unittests/CuTest/test_help_suggestions.c:1).

These full paths refer to the sibling checkout at the baseline revision above.
Do not port its database queries, keyword schema, handler chain, or file fallback.

### Proof

Test inserted, deleted, substituted, and transposed letters; mixed case;
multiword titles; deterministic ties; duplicate-case titles; the five-item cap;
gibberish; tiny, overlong, and non-ASCII queries; and wildcard bypass. Assert
actual link targets as well as visible labels. A selected suggestion must open
the correct page through the dispatcher. Refreshing the catalog must change
future suggestions while preserving already-rendered pager output.

## 3. Give newcomers a clearer starting point

Use three complementary authored pages, keeping them concise:

- **Help:** explain how to search, choose a partial match, and use a typo
  suggestion. Present links to Newbie, Index, Policies, Rules, and the five
  reference-command articles. Link only features already delivered with this work.
- **Index:** organize links by the player's task: movement, combat/fleeing,
  death and corpse recovery, equipment, communication, learning abilities,
  and rules. Give each destination a short description.
- **Newbie:** provide an ordered first-session path: look around and move;
  inspect inventory/equipment; communicate; consider opponents and learn to
  flee; understand death/corpse recovery; find personal abilities; read rules.
  Explain Duris's PvP expectations accurately and avoid unsupported promises
  about safety, starting gear, death replacement, or which race to choose.

Use the verified destination titles `Exits`, `Look`, `Consider`,
`Flee`, `Death`, `Corpse`, `Get`, `Equipment`, `Inventory`, `Wear`, `Wield`,
`COMMUNICATIONS UTILITIES CHANNELS`, `Nchat`, `Say`, `Practice`, `Cast`,
`Memorize`, `Policies`, and `rules`, plus the command articles in section 5.
There are no exact general-purpose `Movement` or `Combat` titles in the two
maintained catalogs at baseline; use those words as section labels rather than
create broken links to them. Teach basic direction commands in Newbie and link
to Exits/Look. The existing Directions article is a hometown-route directory,
not an explanation of walking; do not present it as the basic movement guide.
`rules` comes from the separate rules file.

Convert selected navigation to explicit `[[topic]]` references. Keep surrounding
prose useful without colors or clicks. Avoid a new category taxonomy: authored
sections already satisfy the navigation requirement.

Update the corresponding Help/Index/Newbie entries in both maintained help
sources, and the startup Help source `lib/information/help`, so import order
cannot reintroduce conflicting guidance. Preserve the current parser shapes,
topic delimiters, and edit-date/header format; update dates for edited content.
Follow the shared formatting rules and add no attribution lines.

## 4. Make important pages practical

The initial required content batch is the three hubs, the destination articles
listed in section 3, and the reference-command articles in section 5. Audit
every page in that batch and edit missing or incorrect guidance; already-correct
explanations can be retained. This defines a complete first delivery without
requiring a rewrite of all help topics.

For each actionable topic, present:

1. A short purpose statement.
2. Supported syntax and one concrete example; mark placeholders clearly.
3. Requirements, targets, costs, and important consequences that actually apply.
4. Common reasons the action fails and what the player can do next.
5. A small set of related help links and applicable live reference commands.

Concept articles such as Death/Corpse explain the sequence and recovery steps;
do not invent a command named after the topic. Rules navigation explains where
to read policy without changing policy text. Keep `lib/information/rules` as its
single content owner; review the existing `LAWS RULES` pointer and Policies hub.

Before writing mechanics, trace the dispatcher registration and owning handlers:

- Movement/looking: [`actmove.c`](../../src/cmd/actmove.c) and
  [`actinf.c`](../../src/cmd/actinf.c).
- Considering/fleeing: `do_consider()` in `actinf.c` and
  [`do_flee()`](../../src/cmd/actoff.c).
- Death/corpse recovery and item use: follow the current death path in
  [`fight.c`](../../src/combat/fight.c) and the actual container, wear, and wield
  handlers in [`actobj.c`](../../src/cmd/actobj.c).
- Communication: the registered handlers in [`interp.c`](../../src/cmd/interp.c),
  including `do_nchat()` in [`actwiz.c`](../../src/cmd/actwiz.c).
- Learning/casting: [`guild.c`](../../src/guild/guild.c),
  [`memorize.c`](../../src/classes/memorize.c), and the registered spell-interface
  handlers. Do not imply every class uses `cast` or `memorize`.

Follow [HELP_STYLE_GUIDE.md](../content/HELP_STYLE_GUIDE.md): useful units,
one blank line around headings, readable terminal width, accurate active/passive
distinctions, and source-checked costs and failure conditions. Add relevant
examples without stripping existing valid mechanics or progression information.

## 5. Connect help to current reference commands

Give each command article a clear distinction between personal information,
general reference, and actions. Use these source-verified forms:

- **Innate:** `innate` lists personal grants, unlocks, passive markers, and
  readiness. `innate info <name>` explains access/status and available mechanics;
  for example, `innate info reflection`. `innate list player` provides the wider
  player reference; describe `innate list all` separately. Explain that
  `innate <name> [arguments]` can activate an ability. Update both Innate and the
  existing Innates pointer. Source:
  [`innate_info()`](/home/aiwithapex/projects/duris/src/classes/innates.c:1217),
  [`do_innate()`](/home/aiwithapex/projects/duris/src/classes/innates.c:4462).
- **Class:** `class`, `class list <race>`, `class info <class or specialization>`,
  `class specs <class>`, and `class innates <class or specialization>`.
  Examples: `class info warrior`, `class specs warrior`. Source:
  [`class.c`](../../src/cmd/class.c).
- **Race:** `race`/`race list`, `race info <race name>`, and
  `race innates <race name>`. Example: `race info grey elf`. Explain creation
  availability separately from reference access. Source:
  [`race.c`](../../src/cmd/race.c).
- **Skills:** `skills` for personal proficiency/unlocks;
  `skills <class or specialization>` for definitions;
  `skills info <skill name>` for details. Examples: `skills warrior`,
  `skills info bash`. Source: [`skills.c`](../../src/cmd/skills.c).
- **Spells:** `spells` for the personal list;
  `spells <class or specialization>` for the reference catalog;
  `spells info <spell name>` for details. Examples: `spells cleric`,
  `spells info fireball`. Access, preparation, and readiness are separate facts.
  Source: [`spells.c`](../../src/cmd/spells.c).

Link these articles from all three hubs and the relevant learning, equipment,
and ability pages in the selected batch. Show command examples as visible text
next to clickable help references, for example:

```text
Read [[Innate]] for usage. Type: innate info reflection
Read [[Spells]] for the spell browser. Type: spells info fireball
```

This uses existing link permissions and satisfies navigation without adding
direct executable links to other commands. Never dispatch a reference command
automatically while rendering help: some reference commands read help themselves.

For the selected pages, replace unnecessary copies of changing grant tables
with pointers to the authoritative browser when this does not remove required
standalone help information. Preserve existing class/spec progression contracts
and prose consumers; a wholesale migration of those pages to generated sections
is separate work. Do not claim that all innates have mechanics providers or that
reference visibility means the character can use the ability. Maintain separate
staff-only syntax where it already exists, outside the newcomer path.

## Delivery sequence and files

### A. Search behavior and its regression coverage

Implement sections 1 and 2 together in `src/cmd/wikihelp.c`, with constants in
the existing header only where necessary. Update `docs/content/HELP_SYSTEM.md`
and result-bound wording in `docs/operations/help-cache.md`.

Extend `tests/async/test_help_cache.py`, `help_output_checks.inc`, and
`test_word_output_integration.py`. Their extraction lists must include any new
local production helper. Update assertions that currently expect 101 displayed
results to the explicit 100-alternative contract. Retain the existing large-page,
Unicode, redirect, metadata-budget, and frozen-pager coverage.

### B. Starting pages, practical content, and reference navigation

Implement sections 3-5 as one coherent content batch in:

- `help/duris_help_parsed.hlp`;
- `lib/information/help_index`;
- `lib/information/help` for matching default help guidance;
- `docs/content/HELP_STYLE_GUIDE.md` only for conventions this work establishes.

Use the effective import order when checking every new link. Keep mirrored
entries aligned and leave Rules in its existing owner. Extend the current
content tests with a focused manifest of this batch's required topics and links;
do not build the broader audit tool from the ideas document. Validate actual
imported titles, including compound headings, rather than splitting words into
fictional aliases. Record which existing pages already met the practical format.

### C. Qualify the complete player path on MariaDB

Add a focused `tests/async/run_help_navigation_journey.py` using the existing
fixture/account/authority helpers from `run_class_command_journey.py` and
`test_flight_network_journey.py`. This new file is justified by the combined
import -> lookup -> suggestion -> navigation behavior, which a string test
alone cannot prove. It must import copied fixture sources into disposable
MariaDB and boot the native server there.

For an ordinary character: open `help`, `help index`, and `help newbie`; visit
each task section's destinations; submit the typo example and select its returned
help command; exercise the five reference commands with the examples above.
Verify that `innate info` leaves ability state unchanged and that unavailable
personal abilities still yield useful reference output. Exercise a suitable
active-innate owner as well as a character without that innate.

While one client repeats typo misses, check another client's ordinary command
responses for material delay. Add a synthetic broad-match fixture for the exact-match cap case, and test
`info` through the same lookup route. Check paging enabled/disabled, an MXP
suggestion target, and generic plain output. Use existing output integration
coverage for frozen replay and structured link serialization, with a new
suggestion result as input. If claiming browser click behavior, verify it in the
connected client too; serialized metadata alone proves only the server contract.

## Required validation when implementing

Run the smallest affected tests while editing, then these completion checks:

```sh
python3 tests/async/test_help_cache.py
python3 tests/async/test_word_output_integration.py
python3 tests/async/test_reported_latency_contract.py
python3 tests/async/test_help_layout.py
python3 tests/async/test_help_import_live_parser.py
python3 scripts/format_help_topics.py
./scripts/import_help_to_prod.sh --dry-run
./scripts/format.sh --check
make -C src
```

Run the relevant existing class/race content contracts for any affected mirrors,
and the existing innate/reference-command regressions if their owning code is
changed. The new complete journey, after it exists, runs as:

```sh
bash tests/async/with_disposable_mariadb.sh python3 tests/async/run_help_navigation_journey.py --server bin/server/dms_new
```

Match its CLI to the existing `--server` journey convention. Reuse disposable
MariaDB authority; do not borrow the checkout's player data or credentials.
`test_mariadb_help_catalog.py` currently exercises a flat-file information reader
despite its filename, so it is not evidence of a MariaDB help import/refresh.
The new real-server journey supplies that evidence.

Benchmark ordinary and maximum-size typo misses without sanitizer overhead;
record hardware/build, query/title lengths, median, tail, and worst observed
duration. Confirm no database acquisition, character wait, or cross-player
stall. Do not accept an unmeasured claim of instant search at the catalog limit.

When publication is separately authorized, use the existing transactional import
and `page help`/`page help status` procedure. Verify the selected environment,
review the dry-run and source differences against current database edits, and
confirm a new published catalog generation and the three actual hub pages.
A file edit or queued refresh is not proof of publication. Keep deployment
checks separate from local implementation completion; do not wait for hosted CI
in place of native tests and required review.

## Acceptance checklist

- [x] Exact titles open first across the full catalog; partial matching,
  wildcards, redirects, bounded alternatives, and overflow wording work.
- [x] Misses offer at most five deterministic, useful suggestions; selecting
  one opens its title, with readable plain output and valid semantic links.
- [x] Help, Index, and Newbie cover movement, combat/fleeing, death/corpse
  recovery, equipment, communication, ability learning, and rules through
  working imported destinations.
- [x] Every page in the defined initial batch has been reviewed for practical
  purpose, usable syntax/examples, applicable requirements/costs, failure
  guidance, and related reading; concept pages use appropriate recovery steps.
- [x] Innate, class, race, skills, and spells guidance matches their real
  commands, distinguishes browsing from activation/readiness, and is reachable
  from all three hubs. Existing prose and progression consumers remain correct.
- [x] Focused executable checks, formatting, native build, complete disposable
  MariaDB journey, and bounded-search measurements pass. Report any unrun client
  validation and do not claim broader coverage than was exercised.

## Original planning verification

The planning task checked the current lookup/cache/link code, innate and other
reference-command dispatchers, authored hubs, actual importer parsers and topic
ownership, existing tests, and the Luminari reference locations. No gameplay or
content implementation, build, runtime test, import, or deployment was performed
for this plan. The acceptance boxes intentionally describe future implementation.

## Implementation handoff (2026-11-12)

Working checkout: `/home/aiwithapex/projects/duris-help-improvements` in WSL.
Current branch: `branch/help-navigation-journey`. The original Windows checkout
in the request disappeared externally during read-only discovery; its last
native Git status was clean. The same branch was recovered into this separate
checkout with `git worktree add --force`. No user changes were discarded.

Review stack (merge in this order; do not deploy):

1. [PR #1033](https://github.com/LuminariMUD/Duris/pull/1033),
   `branch/help-improvements-plan` -> `master`, commit `a05bb19f4`;
   labels `bug`, `enhancement`. Full-catalog exact lookup, 100 alternatives,
   overflow notice, whitespace handling and five deterministic typo suggestions.
2. [PR #1034](https://github.com/LuminariMUD/Duris/pull/1034),
   `branch/help-player-navigation` -> `branch/help-improvements-plan`, commit
   `698eb3317`; labels `documentation`, `enhancement`. All 28 selected topics,
   mirrored catalogs, startup Help, live reference guidance and parser contracts.
3. [PR #1036](https://github.com/LuminariMUD/Duris/pull/1036),
   `branch/help-navigation-journey` -> `branch/help-player-navigation`, implementation
   commit `e222187ad`; labels `enhancement`, `documentation`. Native journey,
   complete catalog benchmarks and the common-prefix distance optimization.
   All three PRs are pushed and open for review; no required work remains.

### Scope and source audit

Ablation retained A-C and all acceptance proof. The existing immutable catalog,
semantic links, pager, authoring formats and transactional import remain the
only production path. No schema, index, service, query cache, protocol change,
new command permission or general content-audit framework was added. Local
bounded spelling helpers have one production caller. Qualification found two
necessary performance repairs: reject wildcard retries whose remaining tokens
cannot fit, and strip equal prefix/suffix spans before bounded edit distance.

All 28 selected pages were reviewed. Class, Race, Skills, Spells and the
communications overview already had useful mechanics/reference descriptions,
staff syntax and privacy guidance; those were retained and completed with
examples, failure/access guidance and links. Other selected pages needed
rewriting or expansion. No class/spec progression tables or Rules policy text
were changed. The actual importer parsers check the complete selected manifest,
mirrored bodies, hub reference examples, imported link targets and Rules owner.

Mechanics traced: interpreter registrations; actinf new_look/exits/consider and
inventory/equipment; actmove movement failures; actoff eligible random flee
exits, control flee and vitality costs; actobj get/container/wear/wield and
hand/training rules; actcomm say; actwiz nchat; guild practice and scribing;
memorize preparation/books; sparser parse_spell/do_cast; fight corpse/death,
limits XP threshold and nanny RENT_DEATH routing/waiting-area exceptions.
Corrected Cast's double quotes (single apostrophes required), Memorize's prayer
book claim, Flee's nearest-exit claim, obsolete startup Help split, incomplete
Policies and unsupported newcomer race/gear promises. Reference commands are
visible text beside help links, never automatically executed.

### Verification and measurements

Passed commands:

- `python3 tests/async/test_help_cache.py` (production matcher/lookup/render;
  late exact title, 0/1/100/101 boundaries, ranking, deduplication, bypasses,
  256-byte titles and bounded-distance comparison with a reference matrix).
- `python3 tests/async/test_word_output_integration.py` (real command/output,
  generic/MXP suggestions and returned targets, frozen paging and miss logging;
  existing Unicode/large-page/redirect/metadata coverage retained).
- `python3 tests/async/test_reported_latency_contract.py`.
- `python3 tests/async/test_help_layout.py` and
  `python3 tests/async/test_help_import_live_parser.py`.
- `python3 scripts/format_help_topics.py`, `./scripts/format.sh --check`,
  `git diff --check`, and `make -C src -j4`.
- `python3 tests/async/test_class_helpfiles_contract.py`,
  `python3 tests/async/test_race_helpfiles_complete.py`, and
  `python3 tests/async/test_race_innate_help_sync.py`.
- Full `import_help_to_prod.sh --dry-run` with explicit dummy `help_preview`
  settings at loopback port 1; no checkout .env, DB connection or publication.

Wildcard equivalence uses an independent LIKE matrix for every query up to four
characters over `aA%_` against every title up to four characters over `abA`.
The original long-prefix benchmark exceeded its 30-second harness deadline
before the remaining-length repair. A later loaded-host run approached a
250 ms pulse before the equal-end distance optimization; the final measurements
below supersede the intermediate numbers.

Reproduce: `HELP_BENCHMARK=1 python3 tests/async/test_help_cache.py`.
GCC 13.3.0, C++20 `-O2`, no sanitizer, WSL2 Ubuntu, Intel Core Ultra 9 285H
(16 exposed CPUs), shared host load, 101 samples per complete lookup/miss.
The logger is stubbed; ordinary lookup, fuzzy selection and formatting are timed.

- Effective maintained import: 2,458 titles, title lengths 2-69 bytes, query
  `firball` (7 bytes): median 0.204 ms, p95 1.849, p99 6.431, max 11.051 ms.
- 20,000 14-byte titles/query: median 11.989 ms, p95 32.917, p99 48.846,
  max 51.687 ms.
- 20,000 256-byte titles/query with a 250-byte common prefix: median 67.822 ms,
  p95 120.878, p99 135.363, max 142.361 ms (below the default 250 ms pulse).

### Native player journey: passed

Run:
`bash tests/async/with_disposable_mariadb.sh python3 tests/async/run_help_navigation_journey.py --server bin/server/dms_new`

It imports copied sources into a newly migrated disposable schema, boots the
native minimal world and creates its own accounts. A Human/Warrior lacks
reflection; a Gnome/Warrior owns it at level 31 (innates.c). Staff exists only
inside the fixture. The first native runs passed hubs/destinations, help/info
exact-boundary checks, plain/MXP suggestion follow, paging and reference/state
checks, then exposed test expectations that confused a bounded wildcard list
and a single substring match with exact/fuzzy output. Those assertions were
corrected without changing working product behavior. The final full run passed after those assertion corrections. Saved state waits for the real writer's
`Saving` acknowledgement; a first active use proves info consumed no readiness.

The complete final run passed with 2,610 fixture pages and catalog generation 2.
It exercised all three hubs plus 26 destinations (including the single-owner
Rules page), help/info late exact lookup, wildcard output, generic/MXP suggestion
following, enabled/disabled paging, the five live reference command paths,
reflection owner/non-owner state, actual catalog refresh, and simultaneous clients.
The Gnome's first active reflection use still succeeded after info; subsequent
info calls left the saved effect/innate-use projection unchanged and kept resting
status. The non-owner received mechanics without acquiring the ability.

On the native development build (`-Og`, normal 250 ms pulse), another client's
`look` plus ordered `score` response fence measured:

- Baseline (8 samples): median 504.73 ms, p95 517.64, max 523.62 ms.
- Concurrent repeated typo misses (16 samples): median 508.25 ms,
  p95 525.02, max 535.05 ms.
- The miss client's own command/fence (16 samples): median 505.84 ms,
  p95 523.38, max 525.80 ms.

Those wall times include two input/pulse turns, socket delivery and the score
fence; they are not handler CPU time. Loaded maximum rose 11.43 ms over baseline
on this run, below the journey's three-pulse material-delay allowance. Search
helpers/command checks confirm no command-time SQL or character wait. Evidence
is reproducible through the command above; the last JSON is in ignored
`bin/tests/help-navigation-evidence.json`. Disposable server/schema/container
cleanup completed. No live accounts or credentials were used.

No browser/client UI click test has been run; MXP and structured-output checks
prove the server contract only. All planned implementation outcomes and checks
are complete. Leave the PR stack for review; no CI wait or merge is needed.
No live publication, deployment, release or tag was performed. Publication still
requires separately authorized import/refresh and source/database reconciliation.
