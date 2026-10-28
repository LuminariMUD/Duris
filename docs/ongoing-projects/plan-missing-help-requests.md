# Missing help requests: capture and review plan

Status: proposed; source investigation complete, implementation and gameplay
acceptance pending. Prepared 2026-10-27.

## Outcome and recommendation

Keep a local text record of unsuccessful `help <input>` searches so maintainers
can identify missing help topics and aliases. **Duris already implements the core
capture behavior**, in both maintained persistence builds, at `lib/etc/help`.
Use and qualify that implementation instead of porting a second logging system.

The remaining work is focused regression coverage and a documented review
workflow. No production source change is expected unless that verification finds
a failure in the existing path. This document is a plan, not an implementation
or a claim that the running production server has been checked.

Non-goals: new help content, changing search matching, collecting player/account
identities, a database table, a second log, a background service, automatic issue
creation, deduplication during play, or a new in-game staff command. Production
deployment and changes to existing runtime records are separate work.

## What Luminari-Source does

The sibling checkout is `../Luminari-Source`, at
`/home/aiwithapex/projects/Luminari-Source`. Inspected revision:
`56fca2e452ce0c4186f827812ea8334d6546fb4e`.

1. [`do_help` in `src/core/help.c`](https://github.com/LuminariMUD/Luminari-Source/blob/56fca2e452ce0c4186f827812ea8334d6546fb4e/src/core/help.c#L1938)
   handles an empty request with the default help screen. Otherwise it preserves
   the original argument while its handler chain tries authored content and
   generated game-mechanic help.
2. The final
   [`handle_soundex_suggestions` handler](https://github.com/LuminariMUD/Luminari-Source/blob/56fca2e452ce0c4186f827812ea8334d6546fb4e/src/core/help.c#L1846)
   reports a miss when no partial help was displayed. It calls `mudlog` with
   `file = TRUE`, recording `<character> tried to get help on '<raw input>'`.
   Suggestions can still follow that recorded miss. A displayed partial help
   entry suppresses the miss record.
3. [`mudlog`](https://github.com/LuminariMUD/Luminari-Source/blob/56fca2e452ce0c4186f827812ea8334d6546fb4e/src/core/utils.c#L3273)
   writes this message to the main log. The
   [autorun script's `help:0:get help on` rule](https://github.com/LuminariMUD/Luminari-Source/blob/56fca2e452ce0c4186f827812ea8334d6546fb4e/scripts/autorun/autorun.sh#L109)
   extracts matching lines during
   [`proc_syslog`](https://github.com/LuminariMUD/Luminari-Source/blob/56fca2e452ce0c4186f827812ea8334d6546fb4e/scripts/autorun/autorun.sh#L944)
   and appends them to `${LOG_DIR}/help` (default `log/help`). The zero means that
   this extraction rule does not trim the file to a fixed line count. The
   dedicated file is populated when log processing runs, rather than directly
   by each help command.
4. Luminari's
   [`file help` entry](https://github.com/LuminariMUD/Luminari-Source/blob/56fca2e452ce0c4186f827812ea8334d6546fb4e/src/act/act.wizard.c#L6267)
   lets immortals inspect that file through `HELP_LOGFILE`, defined as
   `../log/help` relative to its normal `lib` working directory.

The useful behavior to retain is recording the original unsuccessful query for
later content review. Luminari's handler framework, syslog extraction, character
names, and staff file viewer are not needed to provide that outcome in Duris.

## Existing Duris path

Inspected revision: `7a8c31067647746cbbe4f7f0975987f5fd3a0b27`.

- [`do_help`](../../src/cmd/actinf.c#L7273) passes the argument to `wiki_help`,
  sends its response, and then appends any command-attribute information.
  [`help` and `info`](../../src/cmd/interp.c#L3209) both use this handler.
- The [flat-file lookup](../../src/cmd/wikihelp.c#L147) and
  [database-backed lookup](../../src/cmd/wikihelp.c#L190) already call
  `logit(LOG_HELP, "%s", str.c_str())` exactly in their zero-match branches.
  Both preserve the usual "no help topics that match your search" response.
- [`LOG_HELP`](../../src/core/structs.h#L2288) is `lib/etc/help`, relative to
  Duris's runtime working directory, normally the project root. This is a
  plain text runtime log, distinct from authored help source files.
- [`logit`](../../src/core/utility.c#L858) adds the server-local timestamp,
  `::`, the query, and a newline. It includes no character name, account, or
  address for this call. For example, a synthetic record looks like:

  ```text
  Tue Oct 27 12:34:56 2026::example missing topic
  ```

- The existing [log writer](../../src/core/utility.c#L738) opens in append mode,
  creates missing parent directories when necessary, and closes after writing.
  During normal server operation it runs through the shared worker queue;
  `help` does not need a synchronous file write or a new worker. An open failure
  is reported through `LOG_FILE` without changing the help response.
- [.gitignore](../../.gitignore) already excludes `lib/etc/help`, and
  [HELP_SYSTEM.md](../content/HELP_SYSTEM.md) already mentions it. The basic
  mechanism needs neither a feature switch nor a migration.

Current limits that matter to the plan:

- A miss means **zero search results**, not merely no exact title. An existing
  substring match or list of matching topics is not logged as missing help.
  Preserve each backend's existing matching rules, including database-backed
  `%` and `_` wildcards.
- An empty request opens the default help page. An unavailable database help
  catalog or invalid flat-file catalog returns its existing error before the
  zero-match branch. Broken redirects are not new user-query misses.
- Command attributes can still appear after a missing topic. They are not a
  substitute for the missing explanatory help entry, so retain the miss record.
- Requests are appended individually, including repetitions and `info` alias
  requests. Raw argument spelling and spacing are retained as received by the
  lookup; there is no normalization or duplicate suppression.
- Delivery is best effort through the existing logger. A queued line is not an
  immediate disk acknowledgement, and the writer does not check every write or
  close result. This plan does not promise crash-proof or disk-full durability,
  nor introduce help-specific retries or log rotation.

## Planned work

### 1. Prove which lookups create records

- [ ] Extend [test_help_cache.py](../../tests/async/test_help_cache.py). Its
  current `logit` stub discards all records, so its existing missing-topic
  assertion proves the response but not capture. Record destination and formatted
  message in the fixture and assert exactly one `LOG_HELP` event for a miss.
- [ ] Extend the
  [flat-file runtime harness](../../tests/async/flatfile_help_runtime_harness.cpp)
  with a local recording override of the existing weak `logit` stub. Keep the
  shared [harness stubs](../../tests/async/harness_stubs.cpp) unchanged.
- [ ] In both paths, cover a multiword missing query, repeated misses, and
  literal punctuation/percent characters in a query confirmed absent from the
  fixture. Verify the complete argument is data passed through `%s`, with no
  identity fields or double logging.
- [ ] Verify no help-log event for default help, exact matches, substring/multiple
  matches, unavailable catalogs, and redirect rendering failures. Use a fresh
  process for invalid flat-file catalog cases because that catalog is cached
  for the process lifetime; extend the existing Python runner if needed.

Do not infer failure from rendered output strings in production, add logging
to `do_help`, or change `wiki_help_single`: the existing zero-result branches
already identify the right event.

### 2. Prove the local file behavior

- [ ] Extend [test_log_writer_thread.py](../../tests/async/test_log_writer_thread.py)
  with the real `LOG_HELP` destination under its disposable runtime directory.
  Verify creation when `lib/etc` is absent, timestamp/query formatting,
  append preservation of an existing record, and repeated entries.
- [ ] Start the existing worker and wait with `flush_log_writer()` in the test
  before inspecting the file. Reuse its existing coverage for ordered delivery,
  slow writes, and normal shutdown; do not add a help-specific flush to gameplay.
- [ ] Exercise a destination-open failure using a deterministic filesystem
  fixture, and verify the existing `LOG_FILE` diagnostic and continued caller
  operation. Keep expectations within the logger's current best-effort contract.

These fixtures must use synthetic queries and private temporary runtimes. Never
append test requests to, truncate, or replace the checkout's real `lib/etc/help`.
Keep new compiled test artifacts under `bin/`.

### 3. Document staff review and verify the command path

- [ ] Expand [HELP_SYSTEM.md](../content/HELP_SYSTEM.md) with the path, record
  format, zero-result definition, duplicate behavior, alias coverage, and the
  distinction between asynchronous capture and a successfully written file.
- [ ] Document this small review workflow: inspect the local file, group query
  text after the first `::` delimiter, and use repeat counts to prioritize
  investigation. Normalize case and surrounding whitespace only in the review
  view; keep original records intact. Counts measure requests, not unique people.
- [ ] For each candidate, check existing titles and aliases before deciding
  whether it needs new prose, a discoverable alias, or no change. Follow the
  existing content ownership and import instructions; do not generate or publish
  help automatically from a log entry. Keep raw records out of Git and public
  reports, since users can type arbitrary text into a help query.
- [ ] On an isolated local/dev server with a healthy catalog, run
  `help example-missing-topic-20261027`, repeat it, and run the same query through
  `info`. Confirm the normal miss response and three new records after the
  writer catches up. Also check `help`, a known matching topic, and command
  attribute output without introducing extra records for successful lookups.
  Confirm append preservation across a normal restart using only this fixture.
- [ ] Perform that command journey for both maintained backends. Check
  `ENVIRONMENT` before operating any server and isolate runtime files and ports
  from existing sessions. Record any journey that cannot be run as unverified.

Manual inspection is sufficient for this scope. A reporting script, staff
browser, or retention policy should only be added for a separately established
need; none is required to start collecting or reviewing missing topics.

## Files and validation

Expected implementation edits are limited to the existing help test, flat-file
runtime harness/runner, log-writer test, `docs/content/HELP_SYSTEM.md`, and this
plan's completion record. Leave `src/cmd/wikihelp.c`, `src/core/structs.h`,
`src/core/utility.c`, and `.gitignore` unchanged unless a focused failure proves
an adjustment is needed. No new production module is planned.

Run the focused checks after the planned test/documentation work:

```sh
python3 tests/async/test_help_cache.py
python3 tests/async/test_flatfile_help_catalog.py
python3 tests/async/test_log_writer_thread.py
python3 tests/async/test_documentation_contract.py
./scripts/format.sh --check
git diff --check
```

For touched C/C++ files, follow the repository build requirement with
`make -C src`. If production code changes in a shared help/logging path, also
build the flat-file backend with a separate output to preserve the normal
server binary:

```sh
make -C src PERSISTENCE_BACKEND=flatfile DMS_BINARY="$PWD/bin/server/dms_help_flatfile"
```

Completion requires executable assertions for both lookup branches and the
actual file writer, the isolated command journeys above (or clearly reported
limits), and maintained operator documentation. CI is not a prerequisite.
If those checks pass with the present runtime implementation, close the work
without inventing additional production changes.

## Planning evidence and ablation

This investigation read both checkouts' help paths, Luminari's log-extraction
script, Duris's logger and command registration, the current test harnesses,
and help documentation. Both checkouts were clean at initial inspection.
Runtime logs, player data, production services, and database contents were not
needed to establish the source behavior.

The plan removes the proposed need for a port: Duris already owns the requested
capture path. It retains targeted tests because existing help harnesses discard
logging, and retains operator documentation because the useful outcome is a
reviewable list of future help topics. No implementation, server build, gameplay
test, import, or deployment was performed while preparing this plan.
