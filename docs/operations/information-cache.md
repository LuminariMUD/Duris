# Informational page cache

`credits`, `faq`, and `wizlist` read a memory snapshot instead of querying MySQL
or reading files during a command. Their former shared two-second cooldown is
removed. The first load is requested after world boot; until it completes the
commands report temporary unavailability, without a synchronous fallback.

Greater gods run `page info` after changing/importing these pages. Check
`page info status` until its generation advances: queuing is not completion.
The status includes readiness, generation, an outstanding refresh, and the last
failure. A failed initial load can be retried with the same command. Refresh
does not run the legacy news/MOTD reads. One refresh may be outstanding; concurrent requests coalesce into one follow-up
and supersede the earlier candidate. Each
complete candidate replaces the previous snapshot on the game thread. Missing
pages, SQL errors, or oversized content retain the previous snapshot.

All three pages must exist; an empty page is valid. Each page is limited to
128 KiB. The worker uses an isolated pooled MySQL connection with the pool's
existing acquisition/socket timeouts.
Shutdown joins the worker before database teardown. Pages handed to output are
owned strings; an active pager never borrows a replaceable cache pointer.

Idle workers refresh automatically every 60 seconds; failed loads
retain the old content and retry at the next interval. A blocked worker can delay
freshness. Edit the tracked `lib/information/{credits,faq,wizlist}` sources,
import them into `mud_info`, then refresh. The maintained help importer now
writes credits/FAQ/wizlist to both `mud_info` and `pages` in the same transaction
as the rest of its import. No migration is needed.

Other `get_mud_info` callers were intentionally audited separately:

- Boot reads for news/MOTD/wizmotd remain existing boot behavior.
- The legacy plain `page` news/MOTD/wizmotd refresh remains unchanged.
- The account-creation `lock` read remains direct and keeps its existing
  authorization freshness.
- Generic `send_mud_info` also remains direct rather than silently changing
  unknown callers' freshness requirements.

This uses the same `refresh_cache` state machine as [help](help-cache.md).
The information commands add no burst limiter,
shared cooldown, or character wait; ordinary command scheduling still applies.

Validation: `python3 tests/async/test_information_cache.py` runs held-worker,
publication, command navigation, bounded content and
owned-output tests. The isolated MariaDB harness is
`tests/async/information_cache_mysql_harness.cpp`, compiled with
`src/cmd/information_cache.c`, `-Isrc`, `-I/usr/include/mysql`, `-pthread`,
and `-lmysqlclient`.
Use only a disposable `cache_test` database without a `mud_info` table, with
root / cache-test and `TEST_DB_HOST`; the harness creates and drops its table.
It verifies failures and that 10,000 cached reads acquire no new connection.
These deterministic tests complement the live two-player journey below.

The SQL query replaces oversized content with NULL before transmission, so an
8 MiB source value cannot cause an 8 MiB client receive allocation. Three active
pages and three candidates can coexist (768 KiB of content plus container overhead).
Publish source changes with the importer, which replaces all three database
rows in one transaction.

The MariaDB harness additionally verifies wire-byte bounds and the actual periodic
refresh interval. The importer test covers atomic publication of the information
rows alongside help pages.

## Live acceptance journey

Use two independently created mortal accounts and explicitly select MariaDB
on a disposable loopback database server:

```sh
TEST_DB_HOST=127.0.0.1 TEST_DB_USER=root TEST_DB_PASSWORD='<disposable-password>' \
  python3 tests/async/test_information_cache_journey.py --backend mariadb
```

The SQL journey creates a unique `information_journey_test_*` schema, applies the
normal fresh-bootstrap migrations, and drops that schema on exit. It
uses temporary world data, independent loopback client addresses, local listeners,
and private journals. The test never reads the checkout `.env` or existing player
state. Use LF line endings for the immutable migration files so their recorded
checksums match the repository manifest.

The journey checks all of the following through real command dispatch and output:

- Twelve credits/FAQ/wizlist sequences (36 information commands), each completing
  in less than two seconds and displaying the expected distinct content.
- A second player repeatedly requests `score`; timing starts at command submission
  and ends after the score-specific response and its prompt, preventing a stale
  prompt from producing a false latency measurement. Every response must complete
  within two seconds, with at least twelve samples.
- The first player opens `more credits` and leaves the real pager active while
  content changes and the normal 60-second automatic refresh publishes. The second
  player continues requesting scores and checks FAQ for the new generation.
- Continuing the first player's pager still displays the original generation.
  Quitting it and requesting each information command displays the new content.

The JSON result reports navigation and observer timing, sample counts, refresh
delay, and pager continuity. The observed refresh delay depends on where editing
falls within the periodic interval. These are local regression measurements with
two players and synthetic pages, not production-load guarantees. Deterministic
cache/SQL tests separately establish failure retention, bounds, and zero database
connection acquisitions for 10,000 cached reads; socket timings alone do not prove
the absence of synchronous I/O.

Measured on 2026-09-11 in an isolated Linux container:

| Backend | Three-page sequence maximum | Observer score maximum | Observer samples | Pager survives refresh |
| --- | --- | --- | --- | --- |
| MariaDB 10.11 | 0.751 s | 0.251 s | 60 | Yes |

The MariaDB run completed twelve navigation sequences, observed automatic publication,
and shut down normally.
