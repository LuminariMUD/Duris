# MXP output links

Duris negotiates MXP independently of GMCP. Telnet option 91 enables server-authored
command and URL links in ordinary player output. A GMCP-capable client does not
implicitly enable MXP. WebSocket text does not contain MXP tags.

## Negotiation and recovery

The greeting sends `IAC DO MXP`. A client `WILL MXP` enables the protocol. If the
client refuses with `WONT MXP`, the server tries `IAC WILL MXP` once and accepts
`DO MXP`. This accommodates the two negotiation directions used by MUD clients.
An unsolicited positive reply is acknowledged in the matching direction.
Activation sends `IAC SB MXP IAC SE` followed by `ESC [ 7 z` (locked mode).

Duplicate positive replies do not repeat activation. `DONT` or `WONT` disables
active MXP and receives the matching acknowledgement. A later positive request
can re-enable it. Negotiation uses the existing fragmented Telnet parser and
binary output queue, including MCCP and pending short writes.

`descriptor_data::mxp_state` is connection-local. Native copyover version 22
appends one retained enabled flag after the complete version 20/21 descriptor
record. Readers still accept versions 12–21 at their original record widths;
those records default to disabled and negotiate before emitting tags. Established
version 22 sessions retain MXP on the original connection. TLS and WebSocket
connections remain outside native copyover's retained-connection contract.

## Text and links

Only explicit output-link records create clickable command links. Command records
are currently limited to `help <topic>` and reject control characters, semicolons
and MXP's `|` command-menu separator. URL records accept `http://` and `https://`.
Producers pass a target separately from the displayed label. Ordinary player text
that resembles a tag or a help reference does not create a command link.

The queue and pager store ordinary Duris markup with optional owned byte spans.
Styling and whole-command budget fallback rebase those spans. At delivery, the
link frame converts them to visible Unicode code-point ranges after the terminal's
`$$` normalization. Generic terminals normalize after color removal.

The renderer emits `<SEND HREF="...">` for help commands and `<A HREF="...">` for
URLs. Every generated tag is emitted in secure mode (`ESC [ 1 z`), immediately
returning to locked mode. Labels and ordinary text stay in locked mode. Targets
escape `&`, `<`, `>`, quotes and apostrophes. Newlines and page boundaries close
the current link; the next portion opens the same target independently.

Raw input cannot switch MXP modes: escape controls outside the SGR and existing
cursor/screen CSI allowlist (`m`, `C`, `D`, `H`, `J`, `K`, `r`, `s`, `u`) display
as `^[`; other C0/C1 controls display as `?`, with newline/tab retained. In
particular, authored `ESC [ ... z` mode changes remain blocked.
Literal angle brackets and ampersands in labels remain literal text. Labels and
targets never become raw executable code or HTML. Clicking a command remains a
client action that submits normal game input through the existing interpreter.

Up to 128 records and 32,768 aggregate target bytes are retained per metadata set,
enough for all 101 help-search results at the catalog's 256-byte title limit.
Command targets remain under `MAX_INPUT_LENGTH`; URL targets have a 2,048-byte
limit. Invalid ranges, overlapping records, invalid targets or excess metadata
leave the text readable without the rejected decoration. If a rendered block's
tags would reach `MAX_STRING_LENGTH`, the renderer emits its complete ordinary
terminal representation without links. It never sends half a generated tag.

Snooped output carries rebased semantic spans through the existing cyan `%`
prefixes and carriage-return removal. Each snooper renders those records using
its own capabilities. Logs retain original text, and pager replay does not log
the message or resolve its targets again.

## URL text recognition

The shared server recognizer accepts explicit, case-insensitive HTTP/HTTPS
schemes and a nonempty authority. It scans visible Unicode text, so Duris color
changes within a scheme, host or path do not change the target. It does not infer
bare domains or other schemes, nor create a URL inside an explicit help link.

Whitespace, controls, quotes, angle brackets, backticks and backslashes end a
candidate. Trailing `. , ; : !` and unmatched trailing closing parentheses,
brackets and braces are excluded; balanced delimiters and trailing `?` / `#`
are retained. No URL is inferred by joining separate sends or a real newline.

Parameter spellings such as `&name=two`, `&n=x` and query flags such as
`&no-cache` take precedence over similarly spelled Duris colors while parsing
URL text. Existing color codes remain valid elsewhere and within URLs. A bare
parameter spelled exactly like a color reset remains ambiguous in Duris markup;
the existing literal-ampersand form `&&nn` displays `&n` in that case. Canonical
serialization applies that escaping before slices lose their original scheme.

New sends enter through `write_output()` or the normal player send boundary;
they infer targets before coalescing/paging. `write_linked_output()` and prepared
output contexts retain already frozen spans, including empty rejected metadata.
Thus a page/chunk keeps the original complete destination, and an oversized
rejected URL cannot reappear as a shorter fragment link. Large help chunks map
from the full page's character offsets. News acceptance counts the canonical
bytes actually admitted to the existing command accumulator.

Non-ASCII URL target bytes are percent-encoded UTF-8 in MXP attributes, keeping
destinations intact through CP437 terminal conversion. Display labels keep their
normal terminal character conversion. Help commands retain normal client input
encoding and command dispatch.

## Verification boundaries

`test_word_output_integration.py` executes the production send, styling, queue,
pager and output-loop bodies. It covers both sender/snooper capability states,
literal text and forged controls, escaping, line/page balance, refresh and size
fallback. Its MXP observer verifies wire modes and visible text; it is not a
replacement for native-client testing.

`test_telnet_output_runtime.py` executes the actual parser, negotiation and writer
with fragmented replies, refusal/re-enable/duplicates, independent GMCP state,
short writes, TLS and MCCP. `test_copyover_evidence.py` exercises the descriptor
producer and native record versions 12–22. Native-client clicks and original-socket
hotboot behavior require the corresponding running-client journeys.
