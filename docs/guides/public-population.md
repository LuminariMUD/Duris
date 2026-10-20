# Public population privacy

[Issue #207](https://github.com/LuminariMUD/Duris/issues/207) protects current
opposing-faction and global presence, except for the in-game `who` messages
indicating whether goods or evils are online. The MUD otherwise omits these
public statistics; the paired DurisWeb change publishes an existing historical
hourly estimate.
The MUD retains an in-memory snapshot of the existing socket peak after a
completed server-relative 60-minute interval. There is no persistent history
store or new publication timer.

| Surface | Population definition and access | Behavior |
| --- | --- | --- |
| Telnet MSSP | Previously current playing mortal descriptors, counting switched originals, before login | Not advertised; unsolicited `DO MSSP` receives `WONT` once per connection. WebSockets emit nothing. |
| Ordinary `who` | Faction-visible characters under existing command filters | Live list and visible count retained; the original good/evil presence messages are restored without names or counts. All players see the prior completed server-hour's peak simultaneous connections once a full hour has elapsed; the current-hour peak is never displayed. |
| Trusted `who` / `world stats` | Live in-game connections, socket peaks and operational faction totals | Unchanged. |
| `lib/reports/status` | Formerly current boot socket peak | Both maintenance and legacy `web_info()` producers now export only game time and uptime. |
| Internal SQL statistics / Redis / authenticated MUD bridge | Live samples and raw character/faction presence | Unchanged; website administration remains privileged. |
| DurisWeb `/api/status` | Previously current Redis presence count | Paired fix replaces `onlinePlayers` with a labeled delayed hourly estimate and explicit window timestamps; unavailable is null. |
| DurisWeb faction charts/date index | Recorded faction counts | Existing completed-UTC-day restriction, minimum 24 hours, retained. |

The `who` connection peak counts simultaneous accepted sockets, including
pre-login connections, not unique logins or faction-specific players. The first
partial hour after boot/copyover is withheld. Clock rollback or a gap of two
hours or more invalidates the old snapshot until another full interval completes.
No live socket peak is exposed to ordinary players.

MSSP requires `PLAYERS` with current logged-in population. A delayed value would
change that meaning, and zero would invent a measurement. MSSP is therefore
disabled, including its otherwise static metadata. Re-enabling it requires a
privacy-compatible agreement with the intended directories; this change claims
no MSSP listing compatibility. Normal login, GMCP and service availability are
unaffected. Reconnects, negotiation changes, restart and copyover cannot restore
a population reply because there is no public population serialization path.

DurisWeb's backend `PUBLIC_POPULATION_DELAY_HOURS` defaults to 6 and accepts
only 3 or 6. Its estimate averages recorded non-trusted playing-character
faction totals over `[floor(now/hour)-delay-1h, floor(now/hour)-delay)`, in UTC.
This is not the former MSSP mortal/original-character definition or a socket
peak. Website and MUD changes must both be reviewed before resolving #207.

Source inspection confirms the old MUD outputs and public API exposed live
signals. No DurisWeb route or static mount serving `lib/reports/status` was
found; that report's external publication remains deployment-dependent. The
producer is protected regardless. The paired website's raw presence feeds are
staff-only, not public statistics.

Verification: `python3 tests/async/test_mssp_runtime.py` executes the production
Telnet parser and responder; `python3 tests/async/test_public_population.py`
executes the production visibility rule, command summary, copyover descriptor
recovery and both report producers with synthetic populations. Recovery checks
cover both factions, staff exclusion, failed restores and later logout/login
counter updates. The latter is not a complete login/gameplay journey.
Run `make -C src` as well. These tests do not establish deployment;
prepared PRs do not alter a running server.
