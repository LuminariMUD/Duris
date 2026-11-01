# GMCP contracts

The same packages use Telnet GMCP subnegotiation and the existing WebSocket
`{type:"gmcp", package, data}` envelope. Legacy gameplay packages keep their
existing defaults. New versioned streams require explicit support and interest.
This document describes the implemented control/time slice of issue #498;
session, item, action and structured command-result contracts are still pending.

## Negotiation and interest

After negotiating GMCP, send:

```text
Core.Supports.Set ["Duris.Capabilities 1", "Duris.Time 1"]
Duris.Subscribe ["Duris.Time 1"]
```

`Core.Supports.Set` replaces supported modules; `Add` and `Remove` update that
set. Only exact implemented name/version pairs grant support. Unknown names
and versions are ignored, so advertising a future schema does not enable it.
Support means the client can decode a stream. It does not subscribe the client.

`Duris.Subscribe` replaces the desired new streams. It requires support for
`Duris.Capabilities 1`; only supported, implemented streams become interested.
An empty array unsubscribes all new streams. Removing stream support also
removes its interest; re-advertising it does not reopen the panel. Removing
Capabilities support clears all new interest and sends one final invalidation.

Each request is an entire JSON array, with no trailing non-whitespace data or
NULs in module names. Requests are limited to 8 KiB including the package name
(and the WebSocket JSON envelope), 64 entries and 96 decoded bytes per entry.
Invalid arrays change no state.
Supports operations share a per-connection token bucket: burst two, refill one
per second. Subscribe has its own bucket. In-range malformed requests consume
tokens too. Oversized or rate-limited requests are ignored before additional
control parsing or construction. WebSocket reuses its already-decoded envelope instead of
serializing and parsing the control data a second time.
No gameplay command, permission, wait or transaction gate is bypassed.

Changes coalesce at the existing two-pulse GMCP flush (about 500 ms). No new
packet is sent to a legacy client that has not advertised Capabilities.
WebSocket's legacy default does not opt it into these new streams.

## Duris.Capabilities, version 1

The server sends a complete control snapshot after supported-module/interest
changes, playing-eligibility changes, initial character snapshots and preference
re-enable/disable:

```json
{"version":1,"enabled":true,"features":{"Duris.Capabilities":1,"Duris.Subscribe":1,"Duris.Time":1},"supported":["Duris.Time"],"interested":["Duris.Time"],"active":["Duris.Time"]}
```

`features` lists implemented contracts only. `supported` and `interested` list
new gameplay streams; the control package itself is implicit in this snapshot.
`enabled` reflects transport negotiation and the character's GMCP preference.
`active` is the effective set, also requiring a playing character. Before entry
it is empty even when interest was already declared. Unverified connections
receive the same public schema metadata; this grants no service/player authority.

Arrays replace their whole scope. A stream absent from `active` invalidates its
client state immediately; absence is not an authoritative empty gameplay list.
The control snapshot precedes newly active time data. Turning off the character
preference still permits this control notification but stops gameplay data.

Telnet DONT invalidates streams through transport negotiation itself. The
connection retains support/interest for DO re-enable and resends current state.
A newly allocated/recovered descriptor starts with no new support or interest.
These fields have no persistent account/character configuration or heap owner.

## Duris.Time, version 1

A complete, connection-scoped game-clock snapshot:

```json
{"revision":"1","hour":9,"phase":"day"}
```

`hour` is 0-23; phases are dawn 04-08, day 09-15, dusk 16-18 and night 19-03.
`revision` is a decimal string, compared losslessly; it advances on observed
hour changes within this server process. Repeated initial snapshots/re-enable
may resend the same revision. A new connection/process establishes a fresh
baseline. There is no character identity, calendar, shutdown deadline or
historical-event replay in this package.

The server builds one small shared payload per changed hour, only when there
is an eligible interested recipient. Entry, subscribe and re-enable send the
current revision; ordinary idle flushes send nothing. Mutations invalidate the
cache after normalized hourly/staff-set changes, without calling do_time(),
world traversal or storage. Staff negative hour input is normalized before
updating the authoritative clock and map phase. No per-second ticks are sent.

Control/time output is bounded below 1 KiB per recipient per flush and enters
the existing transport FIFO. On temporary queue failure the pending snapshot
is retained for retry; later time data cannot overtake a pending control packet.
Existing terminal overflow/connection-close behavior still applies. This slice
makes no replay guarantee across disconnects.

## Proof and remaining qualification

`tests/async/test_gui_gmcp_contract.py` executes the production parser, cache,
bootstrap and framing/send functions with controlled world/transport services.
It covers both transports, unknown versions, malformed/oversized arrays, flood
limits, preference changes, phase boundaries, authoritative control clears,
idle silence and failed-queue retry. Its emitted examples are executable fixture
output; the examples above use the same field shapes.

The GMCP fuzz target exercises the production input handler with ASan/UBSan.
The booted `tests/async/test_gmcp_control_journey.py` journey covers real Telnet
and WebSocket dispatch, character entry/return/reconnect, preference changes,
staff clock mutation and invalid WebSocket module input on disposable state.
Real Mudlet and matched event-loop/serializer measurements remain separate
evidence in `docs/ongoing-projects/plan.md`; these focused checks do not establish
project completion or negligible overhead.
