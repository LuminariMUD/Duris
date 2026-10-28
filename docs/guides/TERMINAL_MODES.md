# Terminal modes

Duris stores a numeric terminal type for each connection. The supported
selection codes are:

| Code | Mode | Behavior |
| --- | --- | --- |
| `1` | Generic | Plain text without ANSI color or structured terminal markup. |
| `2` | ANSI | ANSI color and the normal ANSI login presentation. |
| `3` | MSP presentation markup | Compatibility mode that frames prompts, maps, and group output for clients that understand those tags. |
| `9` | Quick ANSI | ANSI mode without the normal login greeting. |

TERM_MSP is retained as code `3` for compatibility with existing clients.
The terminal choice belongs to the connection: account menus and copyover
preserve it, but a fresh connection normally starts in ANSI. It is not saved
in the character's preferences. In this codebase it is a presentation mode,
not an audio implementation: it does not emit `!!SOUND(...)` or
`!!MUSIC(...)` triggers. Clients should not expect sound or music events from
selecting MSP presentation markup.

The markup currently covers these output areas:

- `<prompt>...</prompt>` around prompts;
- `<map>...</map>` and `<automap>...</automap>` around map output;
- `<group>...</group>` around group output.

In-game, terminal presentation can be selected with `TOGGLE terminal ansi`,
`TOGGLE terminal gen`, or `TOGGLE terminal msp`. The login terminal menu and
its help text use the same codes; leading-zero forms such as `03` and `09`
are also accepted. `TOGGLE terminal` without a value switches ANSI to MSP
and any other mode to ANSI.

MSP and GMCP can be used together. Automatic group updates send one GMCP
snapshot when GMCP is enabled. The MSP frame is sent only when that connection's
displayed group information changes; mana-only updates and changes to a remote
member's undisplayed HP do not repeat the frame. An explicit `group` command
always displays the group, and leaving sends an empty frame to clear it.
The display cache resets on terminal selection, game entry, and new connections
(including copyover recovery).

Explicit map requests still produce text when
`toggle map` is off; automatic maps respect that toggle.

Focused checks: `python3 tests/async/test_terminal_modes_runtime.py`,
`python3 tests/async/test_terminal_modes_contract.py`,
`python3 tests/async/test_word_output_integration.py`, and
`python3 tests/async/test_item_movement_prompt_runtime.py`.
