# Dedicated Discord JSON endpoint

The endpoint is disabled by default. It is separate from player Telnet, TLS,
GMCP, and WebSocket listeners. It accepts one bridge client and only consumes
authentication and heartbeat records. Incoming chat is counted and discarded;
there is no command interpreter or player broadcast path.

This transport chunk exposes `discord_bridge_publish(name, message)` for plain
UTF-8 petition events. **Command hooks are not implemented in this chunk**;
enabling the listener alone does not export player petitions or staff replies.
The cross-repository plan is
[`discord-mud-chat/docs/ongoing-projects/duris-petition-compatibility.md`](https://github.com/LuminariMUD/discord-mud-chat/blob/codex/duris-one-way-mappings/docs/ongoing-projects/duris-petition-compatibility.md).

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
Malformed/non-object/oversized records increment `rejected_records`; oversized
input is discarded through the next LF before parsing resumes.

The connection phase uses `poll(..., 0)` independently of the player readiness
sets, with at most four accepts, 32 read attempts, and 64 KiB of reads per pulse.
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
Fault injection wraps individual syscalls to force short writes/EINTR/EAGAIN;
the listener, parser, serializer, queue, and real socket I/O are production code.
Full game command and isolated game-copyover journeys remain later integration
gates, distinct from this transport's exec/descriptor tests.
