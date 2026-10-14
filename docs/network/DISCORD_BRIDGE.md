# Dedicated Discord JSON endpoint

The endpoint is disabled by default. It is separate from player Telnet, TLS,
GMCP, and WebSocket listeners. It accepts one bridge client and only consumes
authentication and heartbeat records. Incoming chat is counted and discarded;
there is no command interpreter or player broadcast path.

Accepted `petition` commands and staff `ptell` replies export once, outside the
native recipient loops. A petition uses the petitioner name; a reply uses
`Staff -> Player`. Both use `channel: "petition"`. Rejected commands, ordinary
tells, other chat channels, and staff notifications do not export. Native echo,
recipient toggles, logs, terminal output, and GMCP delivery are preserved. Zero
online staff or disabled player echo does not suppress an accepted export.

The Discord destination must be visible only to the intended staff and bot.
Discord posts never become game replies. The feed is optional and best effort;
native petition logs remain the audit record.
The cross-repository plan is
[`discord-mud-chat/docs/ongoing-projects/duris-petition-compatibility.md`](https://github.com/LuminariMUD/discord-mud-chat/blob/codex/duris-game-acceptance/docs/ongoing-projects/duris-petition-compatibility.md).

## Text and concealed identities

The two accepted-command hooks call `discord_petition_export`, which uses native
`AnsiString`/UTF-8 conversion and strips terminal escape sequences (CSI, OSC,
DCS, SOS, PM, APC and single escape commands). LF/tab whitespace, punctuation,
quotes, backslashes, literal `@`, and dollars are preserved; malformed UTF-8
becomes U+FFFD. Player input doubles dollar signs before command dispatch; the
exporter uses native `delete_doubledollar()` on its converted copy so one or
several typed dollar signs remain literal on Discord. Command arguments, native
`act()` rendering, recipient output and audit text are unchanged.
Input names are bounded by `MAX_NAME_LENGTH + 1`; messages by
`MAX_STRING_LENGTH`, both including the terminator. Conversion expands at most
three bytes per source byte, then cJSON escapes the whole record. Overlong
inputs or records exceeding the configured byte limit are dropped whole.

Discord membership has no in-game visibility level. Conservatively replace a
sender or reply target with `Someone` when the character has trusted wizard
invisibility above zero, `AFF_INVISIBLE`, `AFF_HIDE`, `AFF_WRAITHFORM`,
`AFF2_CONCEALMENT`, or `AFF3_ECTOPLASMIC_FORM`. These are target concealment
predicates from `ac_can_see`/`WIZ_INVIS`; no synthetic observer or maximum staff
privilege is assumed. Non-trusted reply senders (including staff using mortal
fog) are also `Someone`, consistent with native player-facing reply output.
Ordinary non-concealed names remain visible. Native per-recipient visibility
and GMCP behavior are unchanged.

## Settings and local use

| Environment setting | Default | Meaning |
| --- | --- | --- |
| `DURIS_DISCORD_ENABLED` | `FALSE` | `TRUE` enables the listener; case-insensitive TRUE/FALSE only. |
| `DURIS_DISCORD_PORT` | `8181` | Dedicated port, 1 through 65535. Always binds `127.0.0.1`, regardless of `LISTEN_ADDRESS`. |
| `DURIS_DISCORD_MAX_RECORD_BYTES` | `1048576` | Maximum bytes before LF, including CR for CRLF; 128 through 1048576. |
| `DURIS_DISCORD_AUTH_TOKEN` | unset | Optional shared secret from the environment. Export stays disabled until valid auth on each connection. |

Build with `make -C src`. In an isolated local test process, set
`DURIS_DISCORD_ENABLED=TRUE` and choose a free dedicated port. Use the Node
bridge with `mud_ip: "127.0.0.1"`, the same port, `mud_tls: false`, and
`direction: "mud_to_discord"` on its only `petition` mapping. Leave both token
variables unset for local plaintext. Do not connect to a gameplay port.

For remote clients, use a certificate-validated TLS terminator forwarding only
to the loopback endpoint. Set Node `mud_tls: true`, the correct certificate
hostname, and the same secret as `MUD_AUTH_TOKEN` in its environment. The local
terminator-to-game hop and trusted local processes are within that trust
boundary. Do not put a secret in JSON or disable certificate checks.

Invalid enabled settings or bind failures leave this optional endpoint closed
and log a startup warning; they do not stop gameplay. Disabled operation opens
no socket and ignores unused endpoint settings.

## Wire and bounded work

UTF-8 JSON objects are followed by LF; CRLF is accepted. Required outgoing
fields are `channel: "petition"`, `name`, `message`, and numeric `emoted: 0`.
cJSON handles escaping. Incoming `auth` uses `message` as the token; a bad token
closes the client. `heartbeat` with `message: "ping"` is consumed without a
pong. No auth acknowledgment is required. Other records never reach gameplay.
Clients must authenticate within 10 seconds when a token is configured. After
authentication (or connection without a token), a valid heartbeat or auth record
must arrive within 300 seconds; the Node bridge sends a heartbeat every 240
seconds. Deadlines use monotonic time and expire even when no socket is readable.
Partial, malformed, rejected, or unauthenticated heartbeat traffic and outgoing
events do not extend the deadline. Expiry frees the client slot and drops pending
output, so a reconnect starts with fresh parser, authentication, and queue state.
Malformed/non-object/oversized records increment `rejected_records`; oversized
input is discarded through the next LF before parsing resumes.

The connection phase uses `poll(..., 0)` independently of the player readiness
sets, with at most four accepts, 32 read attempts, and 64 KiB of reads per pulse.
At most 32 incoming records are consumed per pulse, including empty or discarded
records. A client exceeding this limit is disconnected before the next record is
parsed; pending output is dropped. This bounds parsing work for tiny-record floods.
No new descriptor is passed to `FD_SET`; high descriptors remain safe. Output
runs in the output phase with at most 32 writes and 64 KiB per pulse. Both
sockets are nonblocking and close-on-exec. Partial writes retain their offset;
EINTR retries consume the call budget and EAGAIN waits for a later pulse.

The queue holds at most 256 complete events and 4,194,308 retained wire bytes.
The whole retained front record counts against the byte bound during a partial
write. Overflow drops the new event. No-client and unauthenticated events are
dropped. Disconnect/shutdown drops pending events and resets parser/auth/queue
state. A new client never receives a previous client's partial record.

`discord_bridge_get_status()` exposes counts; once per minute the game logs
connection/authentication status, queued/sent/dropped events, rejected input,
rejected extra clients, and auth failures. Logs omit text and tokens. `sent`
means the complete record was accepted by the socket, not delivered to Discord.
Disabled calls are no-ops, not dropped delivery attempts.

## Lifecycle and verification

Successful copyover exec closes the listener/client and recreates the listener
in the new process. Failed copyover leaves the old sockets and queued records
usable. Ordinary shutdown closes both sockets. The Node bridge reconnects; no
durable delivery or replay is promised. To roll back, disable the endpoint and
restart through the normal local procedure, or stop the Node bridge.

Run `python3 tests/async/test_discord_bridge_runtime.py` for the real-socket
native harness. It builds under `bin/` without game data or Discord credentials.
Fault injection wraps individual syscalls to force short writes/EINTR/EAGAIN.
An injected monotonic clock checks authentication expiry, heartbeat renewal,
idle expiry, and reconnect without real-time sleeps for the deadlines.
The listener, parser, serializer, queue, and real socket I/O are production code.
Run `python3 tests/async/test_discord_petition_export.py` for the exact production
petition/ptell command bodies with production character types and parser,
synthetic players, boundary output/log/visibility stubs, and the real conversion,
serializer, and listener. Set `SANITIZE=1` to add ASan/UBSan. This tests accepted
and rejected command paths, recipient/echo variations, concealment, text bounds,
and native operation during endpoint outages/overflow. Existing output tests
exercise native rendering separately. The full isolated-game journey below is
distinct from these harnesses.

For the real Node/native boundary, check out the companion bridge integration
branch and install its Node dependencies, then run from this checkout:

```sh
python3 tests/async/test_discord_petition_export.py \
  --node-driver /path/to/discord-mud-chat/scripts/testing/duris-integration.js
```

The runner first executes native command regressions, then supplies the freshly
built harness to the Node driver. Its test-only stdio controls invoke the exact
production commands on synthetic players; the Node transport connects to the
production listener through a loopback fragmentation proxy and an in-memory
Discord sink. It checks accepted petition/reply labels, concealment, native
delivery/audit counts, blocked Discord ingress, direct forged chat, malformed
and oversized recovery, chunking/mentions, reconnect, and native operation after
disconnect/disable. Proxy-injected invalid output tests Node recovery; native
serialization always emits valid records. No real Discord API is called.
`SANITIZE=1` also covers this mode with ASan/UBSan. This is a command-boundary
harness, not a full game boot or copyover journey.

For a real game process, player login, persistence and lifecycle check, run:

```sh
python3 tests/async/test_discord_game_journey.py \
  --node-driver /path/to/discord-mud-chat/scripts/testing/duris-game-sink.js
```

This builds the current flat-file server and fixture inspector under `bin/tests/`
and boots a disposable minimal world with temporary accounts, saved players,
TLS certificates, logs and binaries. It does not read `.env`, connect to the
operator's database, or change a running game. It verifies both commands through
real gameplay sockets and the actual Node relay with an in-memory Discord sink.
Cases cover no staff online, echo off, concealed staff, dollar escaping, rejected
commands, unrelated chat, blocked/forged ingress, saves, reload, bridge disconnect,
disabled restart, and normal shutdown. A deliberately invalid staged executable
forces a real failed `execl`; a subsequent valid copyover must preserve the
original player sockets and let Node reconnect. Native audit entries remain
required during rollback. This is a full server with a minimal flat-file world,
not a live Discord or production-database test.
