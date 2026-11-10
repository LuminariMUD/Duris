# Help System

How in-game help works end to end: source material, import pipeline, and
runtime serving.

## Runtime path (what players see)

The `help` command (`do_help`, `src/cmd/actinf.c`) does two things:

1. **`wiki_help()`** (`src/cmd/wikihelp.c`) - in database-backed mode, searches
   an in-memory catalog of the `pages` table (`help_cache_get()`). A background
   worker loads the catalog after boot and refreshes it every 60 seconds; the
   command itself never queries the database, and until the first catalog is
   published it answers that help is temporarily unavailable. Operation,
   limits and the staff refresh command are in
   [help-cache.md](../operations/help-cache.md).

   Titles match case-insensitively by substring, with `%` and `_` wildcards
   (`WIKIHELP_RESULTS_LIMIT` is 100, `src/cmd/wikihelp.h`). One match renders
   the full entry; multiple matches render the exact match plus "see also"
   links. Misses are logged to `lib/etc/help`
   (`logit(LOG_HELP, ...)`), which is useful for spotting missing topics.
   Entries are stored wiki-formatted; `dewikify()` converts valid `[[topic]]`
   references to cyan labels. `do_help()` attaches the target `help topic` as
   semantic metadata; [MXP](../network/MXP.md) clients can click those references
   and search-result titles. Other clients retain readable colored text.
   Missing/empty closing brackets, empty topics, nested brackets and targets with
   control characters or command/menu separators remain literal readable text.
   Only authored help adopts this syntax; arbitrary `[[...]]` player text does
   not create a command link. Bold `'''text'''` markers continue to be removed.

   Clicking a help link uses the same command route as typing `help topic`.
   A full help command replaces an active page after the normal session/command
   gates; pager controls keep their usual behavior. Targets and text are frozen
   for refresh/back replay, even if the help catalog changes. There is no browsing
   cooldown. Large help output is sent in bounded chunks that retain colors,
   complete Unicode characters and clipped link ranges, including with paging
   disabled. Existing string-only help consumers keep their interfaces and do
   not acquire executable help-link metadata implicitly.

   Two page features are applied at render time (`src/cmd/wikihelp.c`,
   `wiki_help_single()`):

   - **Redirects**: a row with `category_id` 1 whose text starts with
     `Redirect: <target>` is followed to `<target>`.
   - **Dynamic sections**: rows with certain `category_id`s get content
     appended from code/properties, not from stored text: 25 race (classes,
     racial stats, innates), 9 class (allowed races, innates, specs),
     16 spec (races, innates, skills, spells), 10 class-skillset (innates,
     skills, spells). Titles `Multiclass` and `Races` also get hardcoded
     sections. The maintained importer writes category `0` for help-index and
     parsed-help entries, so those imported class/spec pages must include their
     complete lists. Do not assume they receive the category-driven additions.
     A database page explicitly assigned one of the categories above does receive
     those additions; its authored text should not duplicate them.

2. **`attrib_help()`** - appends per-command attributes (stat usage)
    loaded at boot from `docs/lib/information/command_attributes.txt`
    (`src/cmd/wikihelp.c`, boot loader). If the file is missing, only a debug log
    line notes it. Every command name registered in
    `src/cmd/interp.c` has an entry, plus entries keyed by ability names
    that are not commands (`apply poison`, `parry`, ...) which serve
    `help <ability>` lookups. Each entry lists the `GET_C_*` stats its
    handler (or skill-gated helper chain) actually uses; commands whose
    handlers consult no stats keep an empty entry and emit no attribute footer.
    The loader holds up to `CMD_ATTRIB_MAX` entries (1024, `src/cmd/wikihelp.h`)
    and bounds-checks the count, logging and skipping anything beyond the cap.

## Reviewing missing searches

Database-cache lookups append zero-result searches to
`lib/etc/help`; `info` uses the same handler as `help`. A miss means no search
results, rather than no exact title. Successful partial/multiple matches, empty
default help, unavailable catalogs and failed redirect rendering do not become
missing-topic records. Command-attribute output can follow a genuine miss.

The shared logger writes server-local time, `::`, and the original query, for
example `Mon Nov  2 12:34:56 2026::example missing topic`. Repetitions remain
separate records. The help call supplies no character, account or address, but
the query itself is arbitrary user text: keep raw records private and out of Git.
The normal asynchronous log queue is best effort; enqueueing is not a disk
acknowledgement or a guarantee against crash/disk-full loss.

For a manual review, inspect the local runtime file and group text after the
first `::` delimiter. Normalize case and surrounding whitespace only in the
review view, preserving original records. Counts measure requests, not unique
people. Check existing titles and aliases before deciding whether a query needs
new prose, a discoverable alias, or no change. Publish any chosen edits through
the content pipeline below; log entries do not authorize automatic publication.

Capture regression coverage and MariaDB command qualification remain tracked
in [#575](https://github.com/LuminariMUD/Duris/issues/575).

## Content pipeline

```
lib/information/{motd,news,faq,...} ------> mud_info / pages
lib/information/help_index -------------> pages (category 0)
help/duris_help_parsed.hlp --------------> pages (category 0; wins duplicate titles)
docs/lib/information/hints.txt ---------> pages
                scripts/import_help_to_prod.sh
```

`scripts/import_help_to_prod.sh`:

> [!WARNING]
> Despite its name, this script can write to any database selected by `.env`
> or to a remote host supplied with `--remote`. `--local` means a direct connection
> using `.env`, not a development database. Run `--dry-run` first, verify
> `DB_HOST`, `DB_PORT`, and `DB_NAME`, and take a database backup before a live
> import. `--clean` deletes all rows from `pages` before re-importing content.
> The script prompts for confirmation for live and clean operations.

- By default, maps files from `lib/information/` into `mud_info` (motd, news,
  wizmotd, credits, faq, wizlist) and `pages` (help, help.1/2, ship/kingdom helps,
  chaos pouch help, faq, rules, credits, wizlist, hints).
- `hints.txt` now lives at `docs/lib/information/hints.txt`; the script reads
  it from there (the login screen streams it via `src/account/nanny.c`).
- Imports the entries from `help/duris_help_parsed.hlp` and parses
  `lib/information/help_index` inline. Use `--dry-run` for current topic counts
  and collisions.
- **Import order matters**: Section 2 (`help_index`) runs before Section 3
  (`duris_help_parsed.hlp`). Both write with DELETE-by-title + INSERT, so a
  title present in both files ends up owned by `duris_help_parsed.hlp`.
  Titles compare case-insensitively (MySQL default collation). Check both
  sources before adding an entry to `help_index`.
- Title parsing in `help_index`: unquoted titles are truncated at `(` -
  `PURGE (Spell)` stores page title `PURGE`; quoted titles keep everything
  inside the quotes - `"ECHO (IMMORTAL)"` stores the full string. Use
  quoting whenever you need parentheses in a page title.
- motd/wizmotd are cached at boot and re-read by the immortal `page` command
  (level 60+, `src/cmd/actcomm.c`). Database news also publishes on the existing
  one-minute mud-info refresh. Its content
  fingerprint drives the per-character `(news)` prompt marker, cleared by opening
  the news with paging enabled. Imported help pages reach players at the next automatic
  refresh, or at once with `page help`; credits, FAQ and wizlist with `page info`
  ([information-cache.md](../operations/information-cache.md)).
- Content is hex-encoded into `DELETE`+`INSERT` SQL so arbitrary text survives;
  supports `--dry-run`.
- `lib/information/help_index` carries one entry per immortal command
  (everything listed by `wizhelp`, levels 57-62), written against the
  command implementations in `src/`. Bare-command titles
  (`POOFIN (Immortal Command)` -> page `POOFIN`) are exact-match
  discoverable; names colliding with spells/skills are quoted so the
  parentheses survive (`"ECHO (IMMORTAL)"`). Because import deletes by
  title, new entries must never re-use an existing bare title.

### Publishing news only

Use `--news-only` for a news update:

```sh
./scripts/import_help_to_prod.sh --news-only --dry-run
./scripts/import_help_to_prod.sh --news-only
```

This imports only `lib/information/news` into `mud_info.name = 'news'`, preserving
the file's bytes, colors, and line breaks. Other information rows and all help
pages stay unchanged. The source must exist and contain at least one byte;
`--news-only --clean` is rejected. A live import requires an existing InnoDB
`mud_info` table and publishes in one transaction, so an SQL error leaves the old
news intact. It does not require a `pages` table. Connection options and live
confirmation work as for the bulk import, with the selected database displayed
before confirmation.

Dry-run lists the file and byte count without connecting to the database; it
does not compare against existing database text or create a backup. Review the
source and back up the destination before publishing. Without `--news-only`,
even an import without `--clean` overwrites matching information and help content.
After publishing, database-backed news refreshes on the next successful one-minute
mud-info read. Plain `page` (no arguments) requests an immediate refresh.
`page help` refreshes only help pages.

The in-game `news` command displays at most 50,000 bytes, including its heading,
color tokens and website footer. It keeps the newest text, ending at a complete
paragraph or line, and links to `https://duris.sbs/news?tab=mud` for the full archive.
The source file and database row remain complete for the website. Even an archive
larger than the command output buffer is safe to display through this capped view.
The unread marker still tracks the full published content, including archive edits.

## Editing help

- Authoring rules and formatting conventions:
  [`docs/content/HELP_STYLE_GUIDE.md`](HELP_STYLE_GUIDE.md). The style
  guide is spell-oriented (stat header block); immortal command entries in
  `help_index` instead use a `Syntax:` line, a rank/level line, a short
  description, and `See also:` - follow the existing entries there.
- In-game topic text lives in `pages`; the import script is the only write
  path (no in-game editor exists - nothing in `src/` inserts into or updates
  `pages`). Update the source files and re-run the import script; editing the
  database directly would silently diverge from the authored source files. See the
  warning above before importing to a shared or remote database.
- Keep the rules in `lib/information/rules`. The `LAWS RULES` entry in
  `help_index` points there via `help rules`; do not add a duplicate `Rules`
  entry to `duris_help_parsed.hlp`, which would override this source.
- Command attribute changes go in
  `docs/lib/information/command_attributes.txt` and require a server restart
  (loaded once at boot).
- The channels overview, `COMMUNICATIONS UTILITIES CHANNELS` in `help_index`
  (`help channels`), lists every way players talk and says what is logged. That
  is the rule of
  [ADR 0003](../adr/0003-player-privacy-chat-snoop-addresses.md); change the
  entry with the rule, and add a new channel to it. The overview, `NCHAT` and
  `SHOUT` are owned by `help_index`; do not add competing parsed-help copies.

## Related

- PC class rules and source ownership: [CLASSES.md](../reference/CLASSES.md).
- Login hints: `docs/lib/information/hints.txt` read by `nanny.c`.
- Wiki export helpers and formatting utilities live alongside the loader in
  `wikihelp.c`.
