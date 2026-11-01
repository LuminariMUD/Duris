# GMCP contracts

The same packages use Telnet GMCP subnegotiation and the existing WebSocket
`{type:"gmcp", package, data}` envelope. Legacy gameplay packages keep their
existing defaults. New versioned streams require explicit support and interest.
This document describes the implemented control, time, lifecycle and combat
state slices of issue #498. Applied-damage events, item, action and command-result
work remains pending.

## Negotiation and interest

After negotiating GMCP, send:

```text
Core.Supports.Set ["Duris.Capabilities 1", "Duris.Time 1", "Duris.Session 1"]
Duris.Subscribe ["Duris.Time 1"]
```

`Core.Supports.Set` replaces supported modules; `Add` and `Remove` update that
set. Only exact implemented name/version pairs grant support. Unknown names
and versions are ignored, so advertising a future schema does not enable it.
Support means the client can decode a stream. It does not subscribe the client.

`Duris.Subscribe` replaces the desired new streams. It requires support for
`Duris.Capabilities 1`; only supported, implemented streams become interested.
An empty array unsubscribes all new streams. Removing stream support also
removes its interest; re-advertising it does not reopen the panel. Session is
connection control: advertising its version enables it without Subscribe. Removing
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
{"version":1,"enabled":true,"features":{"Duris.Capabilities":1,"Duris.Subscribe":1,"Duris.Time":1,"Duris.Session":1},"supported":["Duris.Time"],"interested":["Duris.Time"],"active":["Duris.Time"],"control":["Duris.Session"]}
```

`features` lists implemented contracts only. `supported` and `interested` list
new gameplay streams; the control package itself is implicit in this snapshot.
`enabled` reflects transport negotiation and the character's GMCP preference.
`active` is the effective gameplay set, also requiring a playing character.
Before entry it is empty even when interest was already declared. `control`
lists negotiated lifecycle control; it remains available before character entry
and while the character preference disables gameplay. Removing Session support
clears this array, invalidating Session presentation without implying an entry.
Unverified connections receive the same public schema metadata; this grants no
service/player authority.

Arrays replace their whole scope. A stream absent from `active` invalidates its
client state immediately; absence is not an authoritative empty gameplay list.
The control snapshot precedes newly active time data. Turning off the character
preference still permits this control notification but stops gameplay data.

Telnet DONT invalidates streams through transport negotiation itself. The
connection retains support/interest for DO re-enable and resends current state.
A newly allocated connection starts with no support or interest. Version-18
copyover preserves eligible live-socket protocol state as described below.
These fields have no persistent account/character configuration or heap owner.

## Duris.Session, version 1

A complete connection/character lifecycle snapshot:

```json
{"context":"0123456789abcdef0123456789abcdef","process":"fedcba9876543210fedcba9876543210","generation":"1","state":"playing","resumed":false,"character":{"name":"Tester","bodyRevision":"1"}}
```

States are `account`, `chargen` and `playing`. Account and chargen snapshots
have `character:null`; temporary creation/load bodies never become an entered
character. No account identifier, credential, player ID or global runtime ID
is included. The name belongs to the authenticated owning player, including
while morphed or switched into an NPC. The opaque context/process markers are
identities, not authentication tokens or permission grants.

The once-per-entry key is `(context,generation)`. Context is unique to the
connection; generation is a lossless decimal string advancing only when that
connection actually enters/attaches a character. Repeated bootstrap, Supports,
DO, or preference re-enable resends the same key. Account/chargen transitions
never advance it. Returning to a character from the account menu advances it,
even for the same name. A new TCP/WebSocket connection has a fresh context.
Consumers must retain their initialized-entry key across stream re-enable and
must not execute saved login actions merely because another snapshot arrived.

`bodyRevision` identifies the controlled body within an entry. Morph, switch
and return change it while retaining the entry key. Consumers invalidate
body-scoped views/continuations on that change instead of treating it as a
new login. It does not expose a prototype or globally enumerable identity.

Ordering is Capabilities, Session boundary, then compatible character data.
Leaving a character sends `character:null` while the old body is still valid;
a direct A-to-B replacement also queues that clear before B's entry snapshot.
Already queued output retains FIFO order. Temporary allocation/queue failure
retains pending control, holds subsequent structured gameplay data and requests
a fresh initial snapshot after recovery; no partial Session object is sent.
Outside playing, Session-aware connections receive no character gameplay
packets; Core control and explicitly opted-in input-receipt metadata remain
available. Normal command/transaction/authentication rules remain unchanged.

Copyover uses version 18 of the existing descriptor record to retain support,
interest, entry context/generation, body revision and input-receipt continuity.
Readers still accept versions 12-17 with their original descriptor prefix;
missing optional protocol state defaults off. No new state file, account
preference or synchronous repository read is added. On supported Telnet/MCCP
hotboot, the entry key is unchanged, `resumed:true` and a new process marker
invalidate process-local snapshot revision baselines. Views resynchronize;
login actions do not rerun. WebSocket/TLS copyover eligibility retains the
existing refusal policy. Ordinary reconnect creates a fresh connection context.

## Duris.Time, version 1

A complete, connection-scoped game-clock snapshot:

```json
{"revision":"1","hour":9,"phase":"day","process":"fedcba9876543210fedcba9876543210"}
```

`hour` is 0-23; phases are dawn 04-08, day 09-15, dusk 16-18 and night 19-03.
`revision` is a decimal string, compared losslessly; it advances on observed
hour changes within this server process. The opaque `process` marker scopes
that revision even for a Time-only client, so a retained socket can reset its
clock baseline after hotboot without requiring Session support. Repeated initial snapshots/re-enable
may resend the same revision. A new connection/process establishes a fresh
baseline. Session-aware consumers use its process marker to reset that baseline
across copyover without creating another entry. There is no character identity, calendar, shutdown deadline or
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

## Combat.Update (legacy-compatible full state)

Every snapshot replaces both `target` and `tank`; each is an object or explicit
`null`. Target is the controlled body's current opponent, only while room-local.
Tank is that opponent's opponent, also only while room-local. Their HP is separate
from `Char.Vitals.hp/maxHp`, which continues to describe the controlled body.

```json
{"target":{"name":"wolf","health":"small wounds","healthPercent":80,"position":"standing"},"tank":{"name":"Ally","health":"awful","healthPercent":5,"position":"kneeling"},"revision":"7"}
```

Percentages are clamped to 0-100 using wide intermediate arithmetic. Overheal
cannot overflow a bar, and negative HP retains the bleeding condition. Position
uses the existing prone/sitting/kneeling/standing model. Names follow the prompt's
viewer policy: unseen subjects become `someone`, players use recipient-specific
PERS, and NPCs use the first alphabetic word. Names are plain text, bounded to
255 bytes; no runtime ID, prototype or raw pointer is exposed.

The existing two-pulse descriptor pass samples only these two subjects and sends
changed views, including healing, posture and non-GMCP tanks. It does not scan a
room or the combat/population list per hit. Repeated unchanged flushes allocate no
JSON; disabled and pre-entry recipients do not resolve subjects. Snapshots retain
only bounded values, so extraction cannot leave a queued victim pointer. Initial
bootstrap resends the current complete state; session/body transitions invalidate
the cache. `{"target":null,"tank":null,"revision":"8"}` clears both views.

`revision` is a lossless decimal string increasing for each accepted Combat.Update
on this connection/process. Rejected state output leaves the cache unchanged for
retry. Session-aware consumers use its process/body boundaries to reset their
revision baseline. Other legacy consumers use their usual reconnect/bootstrap
reset; no historical replay is implied. State-only JSON stays below 4 KiB.

The optional legacy `round` remains a per-applied-hit compatibility field, not a
complete battle log or aggregated combat round. Before the first combat
relationship is established, its immediate snapshot uses the struck victim as
the target, including a lethal first hit. The next periodic snapshot follows the
current relationship and clears absent subjects. State-only updates never repeat
the round. Secondary-hit events, known damage type/critical metadata and the
negotiated event sequence/budget contract remain required in the next dependent
PR. This state slice does not claim those events or the reported client HP
symptom fixed.

## Proof and remaining qualification

`tests/async/test_gui_gmcp_contract.py` executes the production parser, cache,
bootstrap and framing/send functions with controlled world/transport services.
It covers both transports, unknown versions, malformed/oversized arrays, flood
limits, preference changes, phase boundaries, authoritative control clears,
idle silence, lifecycle/body ordering, JSON allocation failure and failed-queue
retry. `--sanitize` enables ASan/UBSan for the full native fixture. Its emitted examples are executable fixture
output; the examples above use the same field shapes.

The GMCP fuzz target exercises the production input handler with ASan/UBSan.
The booted `tests/async/test_gmcp_control_journey.py` journey covers real Telnet
and WebSocket dispatch, character entry/return/reconnect, preference changes,
staff clock mutation and invalid WebSocket module input on disposable state.
The original-socket copyover journey verifies context/generation continuity
with and without MCCP, and the native copyover matrix covers versions 12-18.
Real Mudlet and matched event-loop/serializer measurements remain separate
evidence in `docs/ongoing-projects/plan.md`; these focused checks do not establish
project completion or negligible overhead.
