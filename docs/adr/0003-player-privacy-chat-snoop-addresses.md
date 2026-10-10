# 0003. Player privacy: chat logging, snoop and address retention

**Status:** Accepted and implemented.
**Date:** 2026-10-09 (decided by the owner; decision 1 implemented the same day, decisions 2
and 3 on 2026-10-10)

This records what the game may log or watch of its players, and for how long it keeps their
network addresses. All three decisions are in the code; the Context section describes the
code before them.

## Context

The 2026-10-09 log review (`docs/ongoing-projects/log-review-2026-10-09.md`, last at
`24e7d3fba`) found:

- **Chat is logged wholesale.** `lib/duris.properties` sets `logs.chat.status=1`. Every tell,
  whisper, `ask`, say and emote, every `project` and `beep`, and all guild (`gcc`) and
  alliance (`acc`) chat go to `logs/log/chat` in plain text with both names
  (`src/cmd/actcomm.c`, `src/cmd/actwiz.c`, `src/guild/alliances.c`, the `LOG_CHAT` calls).
  Petitions, the zone-wide `shout`, the newbie channel (`nchat`), `jchat`, and the immortals'
  echoes, `ptell`, `wizmsg` and `gshout` go there too.
- **Snoop never tells the target, and the top two levels leave no trail.** `snoop` needs level
  60 (`src/cmd/interp.c`, `CMD_SNOOP`). `do_snoop()` (`src/cmd/actwiz.c`) tells the target
  only when the snooper is below level 58 at the start, or below 58 or 59 at the end, so no
  target is ever told. It writes the `WIZLOG` audit row only below level 61, so a snoop at 61
  or 62 is not recorded anywhere.
- **Immortals can read a player's recent private messages.** Each player keeps their last
  200 private messages in memory for their own `recall` command. Any immortal can run
  `recall <n> <player>` (`do_recall()`, `src/cmd/actinf.c`) to read another online
  player's, with no notice to the player and no audit. Nothing is written to disk.
- **`cmd.debug` holds what players typed.** With `debug_mode` on (the default,
  `src/core/debug.c`), the last 500 commands are written in full when the server exits or
  crashes, the text of every tell and say among them.
- **Addresses are kept with no limit.** Nothing removes them by age:
  - in files, the log archives (`comm`, `debug`, `player-log/new`) and the reverse-DNS cache
    in `lib/etc/hosts`;
  - in the database, `log_entries`, `account_ips`, `account_login_history`, `ip_info`, and
    the `last_ip` columns of `player_data` and `account_characters`.

  The launcher caps the archives by size (`LOG_ARCHIVE_LIMIT_MB`), not by age.

Retention for these was pending with the rest of the lifecycle policy (finding P00-S08 in
[SECURITY-COMPLIANCE.md](../records/SECURITY-COMPLIANCE.md)).

## Decision

1. **Players may assume a minimal privacy, so their conversation is not logged.** The game
   logs no tell, whisper, `ask`, say, emote, `project` or `beep`, no guild or alliance chat,
   no `jchat` (the general chat of one racewar side) and no zone-wide `shout`. In
   `cmd.debug` these commands keep their command word and lose their text. It logs only:
   - petitions, which are addressed to staff;
   - immortal actions: the echo commands, `ptell`, `wizmsg` and `gshout`, as the staff's
     audit trail;
   - the newbie channel (`nchat`), to find what to improve in the new-player experience.
2. **Snoop is used rarely and carefully, and in nearly every case the target knows.**
   - `snoop` tells the target when it starts and when it stops.
   - A silent snoop is a separate, explicit form, `snoop <name> silent <reason>`, open only
     at level 62. The reason is required.
   - Every snoop is audited at every level, 61 and 62 included: who, whom, start, stop,
     whether it was silent, and the reason.
   - An immortal cannot read another player's private messages: `recall <n> <player>`
     returns at once with "Disabled by Zusuk October 9 2026". A player's own `recall` is
     unchanged.
3. **Network addresses are kept for security for at most 30 days, everywhere.** This covers
   addresses and reverse-DNS names in the log archives, `lib/etc/hosts`, `log_entries`,
   `account_ips`, `account_login_history`, `ip_info`, and the `last_ip` columns, which are
   cleared after 30 days.
   - **Exception:** an address on the ban list is kept while its ban stands; lifting the ban
     removes it.
   - **No longer-lived identifier.** Nothing is kept to recognize a returning player after
     the 30 days: no hashed or truncated address. A banned player who returns after the
     window starts fresh.

## Consequences

- **Implemented for decision 1 (2026-10-09):**
  - Every `LOG_CHAT` call but those for decision 1's three kinds is gone (the switch,
    `logs.chat.status`, is still one for all of them).
  - `cmdlog()` (`src/core/debug.c`) keeps only the command word of a conversation command,
    resolved as the interpreter resolves it, and `'` and `:` with the text glued on.
  - Regression tests: `tests/async/test_chat_log_privacy.py` pins the remaining
    `LOG_CHAT` calls and the withheld commands, and `tests/async/test_command_log_ring.py`
    runs the real `cmdlog()` on a say, a glued `'` and a tell.
  - The one-off purge ran on staging: 31 says and tells left the one archived `chat` log,
    and 2 lines of `cmd.debug` lost their text.
  - The in-game help states the rule: `help channels` lists every channel, who hears it,
    and what is logged.
- **Implemented for decisions 2 and 3 (2026-10-10):**
  - `do_snoop()` (`src/cmd/actwiz.c`) tells the target at the start and at every end of a
    snoop the command started: a stop, a move to another target, a quit, the snooper's
    link closing or the snooper leaving the game; when the target leaves, each snooper
    is told why. `snoop <name> silent <reason>` is level 62 only, and its target is told
    nothing. Each start and end is a `wiz` row in `log_entries` (the flat-file backend
    writes it to the wiz log), with "silently" and the reason on a silent start. The
    channel spell's shared sight uses the same mechanism and is neither told nor audited.
  - `recall <n> <player>` by an immortal answers "Disabled by Zusuk October 9 2026".
  - The `address_retention` job (below) moves the live logs into `logs/old-logs/<date>/`
    once they are a day old, so a server kept up by copyovers archives them too, and
    removes each archived file and `core.*` dump 30 days after its last write.
  - The server clears `lib/etc/hosts` at a cold boot (not a copyover) and removes a
    descriptor's files when it closes.
  - The `address_retention` maintenance job runs hourly. It deletes `account_ips` and
    `account_login_history` rows last written over 30 days ago, and clears the address of
    older `log_entries`, `ip_info`, `player_data` and `account_characters` rows, at most
    256 rows per table a run. The ban list is a file (`lib/misc/ban_sites`) and is left
    alone. An account keeps each address's last use (`account_ips.updated_at`); a login
    no longer gives every address the save's time, and drops one past 30 days. `finger`
    no longer shows an address from a login over 30 days ago.
  - Regression tests: `tests/async/test_snoop_and_recall.py` runs the real `do_snoop()`
    and `do_recall()`; `test_hostname_files_journey.py` boots a server;
    `test_log_retention.py` covers the log files; `run_address_retention_journey.py`
    (in `make test-db`) logs in on MariaDB and runs the prune.
  - The flat-file backend, which no deployment uses, keeps its account address lists and
    IP activity files without an age limit; only what it shows is limited.
- **Docs updated with the code:** the in-game `snoop` help entries, the `recall` entry and
  the privacy lines of the `COMMUNICATIONS UTILITIES CHANNELS` entry in
  `lib/information/help_index`; the personal data inventory in `SECURITY-COMPLIANCE.md`;
  the `log_entries`, `account_ips` and `ip_info` entries in
  `migrations/data_lifecycle_manifest.json`, which take this record as their decision
  reference ([DATA_LIFECYCLE.md](../persistence/DATA_LIFECYCLE.md)).
- **What this record is not.** It is the owner's decision for these data, made as the game's
  operator. It does not decide the lawful basis, and it does not cover the rest of the
  lifecycle policy, which stays pending under P00-S08. It is not a claim of legal
  compliance.
- **DurisWeb.** The website's tables in the same database also hold addresses (page views,
  forum posts and threads, admin and builder logs). The same 30-day rule applies; that work
  belongs to the DurisWeb repository.
