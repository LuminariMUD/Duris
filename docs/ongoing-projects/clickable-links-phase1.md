# Clickable links: Phase 1 implementation plan

Date: 2026-11-09. Status: implementation in progress.

## Outcome and scope

Build a small, coherent output-link framework and ship exactly two uses:

1. Help references and help search results that submit the corresponding help
   command when clicked.
2. HTTP and HTTPS URLs that open in the user's browser when clicked.

Support MXP-capable Telnet clients and the DurisWeb player client. Preserve
readable output for clients that do not support links. GMCP alone is not proof
that a client can render links; negotiate the applicable presentation capability.

The framework must preserve colors, visible text, ordering, paging, replay,
snooping, transport backpressure, and supported hotboot behavior. Link handling
must remain bounded and require no database reads in the output path.

Phase 1 does not add clickable exits, items, mobs, players, shops, action menus,
automatic commands, or gameplay changes. It does not introduce OSC 8 support,
a general markup language, an action registry, or a replacement networking stack.
No database migration or help-content rewrite is expected.

## Workspace and delivery

- Repository: `LuminariMUD/Duris`.
- Base: `origin/master` at `91f40a01fe` when this worktree was created.
- First PR branch: `branch/clickable-links-phase1`.
- Current implementation branch: `branch/clickable-links-web-protocol`, stacked
  on `branch/clickable-links-urls` (then help, MXP, output and the first PR branch).
- Worktree: `/home/aiwithapex/projects/duris-worktrees/clickable-links-phase1`.
- Plan: `docs/ongoing-projects/clickable-links-phase1.md` in that worktree.
- Deliver focused, reviewable commits and PRs as each chunk is verified. Stack
  dependent changes and keep this document current for handoff.
- Companion `DurisWeb` branch: `branch/clickable-links-phase1`, worktree
  `/home/aiwithapex/projects/durisweb-worktrees/clickable-links-phase1`, based on
  `origin/master` at `a21e175`. Its instructions and relevant frontend contracts
  are read; frozen-lockfile frontend dependencies are installed. No client code
  is implemented yet. Keep commits in their owning repositories and link PRs.
- Mudlet should use native MXP for the new scrolling-output links; changing the
  `durisclient` package is not an expected dependency.

The earlier 2-4 hour estimate covers implementation and verification, including
DurisWeb, but is provisional. Reassess after the queue/pager slice below is proven;
do not trade away acceptance criteria to fit the estimate.

## Existing code and reuse points

- [Help rendering](../../src/cmd/wikihelp.c): `dewikify()` currently converts
  `[[topic]]` to cyan text; `wiki_help()` builds search-result titles. The help
  cache remains the source of help content and title matching.
- [Command entry](../../src/cmd/actinf.c): `do_help()` sends the rendered help.
  Other callers use `wiki_help_single()` and `wiki_help_prose()`; preserve their
  plain-text interfaces unless a link-aware caller explicitly adopts metadata.
- [Message construction](../../src/player/output_message.h) and
  [output context](../../src/net/output_style.h) already carry semantic styling
  and protect authored text. Reuse their delivery boundary and freeze-once rules.
- [Queue and delivery](../../src/net/comm.c): output currently travels through
  `send_to_char()`, command accumulation, `write_to_q()`, and `process_output()`.
  Queue entries own strings and can coalesce. Input and output share the queue
  type, so an output change must not alter command-input behavior.
- [Pager](../../src/net/modify.c): pages are slices of an owned frozen string;
  refresh/back replay uses `LOG_NONE`. Link metadata must survive these slices.
  `select_session_input()` currently routes all input to an active pager, where
  `help topic` closes the page and is consumed. Help-link activation must address
  this existing behavior as well as render the link.
- [ANSI conversion](../../src/net/ansi.c) and
  [style serialization budgets](../../src/net/output_style.c) govern visible
  characters, color expansion, and size fallback.
- [Telnet negotiation](../../src/net/mccp.c) handles GMCP, compression and TTYPE;
  it currently has no MXP support.
- [WebSocket output](../../src/net/websocket.c) and
  [JSON envelopes](../../src/core/json_utils.c) already carry ordinary text and
  GMCP. Extend the existing ordered output path.
- [Chat presentation](../../src/net/chat_presentation.c) already serializes
  plain text and color runs using Unicode code-point offsets. Reuse this
  convention and its normalization of visible text.
- [Copyover](../../src/persistence/copyover.c) and its
  [record definitions](../../src/persistence/copyover.h) own retained descriptor
  state and backward-compatible recovery.
- In `durisweb`, inspect `frontend/src/composables/useMudConnection.ts`,
  `stores/mudStore.ts`, `types/mud.ts`, `utils/ansiParser.ts`, and
  `components/mud/{MudActivityLog,ChatPresentation}.vue`. Text is split into lines
  and processed by triggers before storage; the player log is not the admin
  xterm terminal.
- Reference implementation: `Luminari-Source/src/net/protocol.c` at inspected
  revision `77d9b032d`, especially `ProtocolOutput()` and MXP negotiation, plus
  `src/act/act.informative.c` for command links. Adapt the protocol mechanics;
  importing the entire protocol subsystem is unnecessary.

## Architecture decisions

### One semantic representation; render at delivery

Represent a link as a range in visible text plus a kind and target:
`command` or `url`. Phase 1 command producers emit only `help <topic>`.
Labels remain ordinary styled text. Targets are separate from labels and are
never reconstructed from the displayed words at click time.

Use half-open Unicode code-point ranges for wire presentation metadata, matching
the existing structured chat convention. JavaScript consumers must handle these
as code points rather than UTF-16 indices. Internally, `OutputLink` uses byte
ranges in the owned Duris markup, matching queue concatenation and pager slicing.
`rebase_output_links()` maps those ranges when styling or budget fallback changes
the markup. `freeze_output_links()` produces `VisibleOutputLink` code-point
ranges after terminal dollar normalization (including generic terminals). The
distinct types keep byte offsets and visible offsets separate without changing
the existing queue/pager text representation.

Add optional owned link metadata to the existing output lifecycle. Existing
string-only callers continue to work. Keep borrowed builder data synchronous;
anything retained by a queue or pager must own its text and targets. Avoid a
global link-ID registry, descriptor pointer references in payloads, or a second
output queue.

Before converting producers, implement one synthetic linked message through the
real send, accumulation, queue, paging, and serialization path. Coalescing must
rebase ranges; page slices must clip/rebase them and emit balanced links on each
page. Track metadata only where needed, with no allocation per unlinked character.
Document the final ownership fields and offset conversions in code.

### Bounded rendering and literal-text boundaries

Only explicit semantic records can create command links. Player chat, object
names, help prose, and descriptions must not be able to inject MXP tags, terminal
controls, HTML, or client code through labels or targets.

Validate ranges, non-overlap, kinds, target lengths, URL schemes, and control
characters before rendering. Use existing command and message size limits and
define bounded link-count/metadata limits alongside the wire contract. Serialize
MXP attributes and browser content with their respective escaping rules.

Account for tag expansion and snoop prefixes. If decoration cannot fit, retain
the visible text and omit the affected decoration rather than truncate content
or emit half a tag. Link metadata must not enter player logs or command history
as raw wire markup. Render snooped output for the snooper's own capabilities.

Freeze colors and link targets once. Pager refresh/back must not rerun animation,
re-resolve help content, duplicate logs, or advance unrelated output sequences.

### Capabilities and transports

For Telnet, add MXP option 91 negotiation, explicit per-connection state, and
enable/disable handling. Follow the interoperable negotiation pattern in
Luminari, including fragmented input and repeated replies. Use `<SEND>` for
commands and `<A>` for URLs, with controlled secure/locked mode transitions.
Plain clients receive the same visible text without control/tag leakage.
GMCP and MXP remain independent: test either enabled without the other.

For DurisWeb, propose `Duris.Links 1` through the existing `Core.Supports`
negotiation and capability reporting. This is a presentation capability for
existing output, not a periodic stream; it needs no new `Duris.Subscribe` entry.
The name and schema are proposed until documented and implemented together.
Honor support removal and existing GMCP-disable behavior for this path.

Add optional versioned presentation metadata to the existing text envelope,
retaining its legacy `data` and `category` fields. Use the existing structured
chat presentation conventions for text, colors and links, and extend chat output
only as needed for URL coverage. Attach metadata to the exact text it describes;
do not send a separate GMCP message that must be matched to scrolling text later.
Older clients must continue receiving and rendering one copy of the text.

The browser should render escaped text nodes, anchors, and command buttons from
validated segments. Help clicks use the existing game-command sender and normal
server interpreter. Web URLs open only on a user click, with safe external-link
attributes. No `eval`, injected HTML handlers, or new command-execution endpoint.

Preserve or explicitly renegotiate link capability on the existing supported
hotboot paths. Extend the versioned descriptor record if state must be retained;
do not silently change old record sizes. Old records default safely to links off
and negotiate before emitting markup. Test links both before and after hotboot.

## Feature behavior

### Help

- Convert valid `[[topic]]` references into links targeting `help topic`, keeping
  the current label and color. Link each existing help-search result similarly.
- Keep title matching, redirects, missing-topic messages and permissions under
  the existing help implementation. Clicking a link must behave like typing it.
- Make ordinary help commands work while paging: release the current page using
  existing teardown and route the help input through normal playing-command
  selection and dispatch exactly once. Apply this equally to typed and clicked
  help. Preserve pager controls and all action, transaction, editor, login and
  permission gates; do not call the help handler directly from the pager.
- Parse references only in authored help content at its producer. Do not make
  arbitrary `[[...]]` text elsewhere executable.
- Preserve malformed/empty references as readable text. Reject targets with
  control characters or command separators that could submit multiple commands.
- Preserve existing consumers that require prose strings. A bounded rendering
  overload or result type should carry optional link metadata without forcing
  a rewrite of all help consumers or the help cache.

### Web URLs

- Recognize explicit `http://` and `https://` URLs in delivered player output,
  including help, announcements and chat. Use a bounded linear scan of visible
  text; do not guess bare domains or expand other URI schemes in Phase 1.
- Preserve query strings, fragments and literal ampersands. Define and test
  trailing punctuation and balanced-parenthesis handling. A URL interrupted by
  a real newline is not automatically joined across unrelated messages.
- Color changes within a URL must not split its identity. Do not create nested
  or overlapping links where an explicit help link already exists.
- Apply the same semantic URL rules to both output transports and relevant chat
  presentations. Do not add separate regex behavior for each display panel.
- Existing URL text stays visible on unsupported clients; native client URL
  detection may still work independently.

## Implementation sequence and file ownership

1. **Prove the output lifecycle.** Finalize the semantic record and ownership
   model, then carry one linked message through real queue/pager code with
   executable regressions. Expected owners: `src/player/output_message.*`,
   `src/net/output_style.*`, `src/net/comm.c`, `src/net/modify.c`,
   `src/net/ansi.*`, and relevant structures in `src/core/structs.h`.
   Extract a small link module only where both transports need shared logic.
2. **Implement transports.** Add MXP negotiation/rendering, browser capability
   and optional metadata, and hotboot continuity. Expected owners:
   `src/net/{mccp,gmcp,websocket}.*`, `src/net/telnet.h`,
   `src/core/json_utils.*`, `src/net/chat_presentation.*`, and
   `src/persistence/copyover.*`. Reuse current framing/backpressure.
3. **Adopt help and URLs.** Update `src/cmd/wikihelp.*` and the minimal help send
   boundary in `src/cmd/actinf.c`. Add shared URL recognition at the presentation
   boundary and complete fallback behavior. Leave other command displays alone.
4. **Complete DurisWeb.** Negotiate support; decode optional metadata; preserve
   it through trigger processing, newline splitting, storage, live log, split
   history, and chat displays. Rebase ranges for each line; gagged lines must
   discard their metadata. Reuse a small shared renderer for actual consumers.
5. **Verify and document.** Run the checks below and update the actual network
   contract, help syntax documentation, and regression notes. Record client
   versions and any unverified runtime behavior. Keep server and web commits
   independently compatible with the old peer.

## Acceptance and proof

Extend existing executable harnesses rather than creating a parallel testing
framework. New focused link tests are justified for semantics not covered today.

- **Links:** help reference and search-result clicks submit exactly one correct
  help command, including during active paging; typed help follows the same
  route. URLs open the exact allowed destination; output never initiates an
  action by itself. Broken references remain readable.
- **Rendering:** colors, Unicode including non-BMP characters, literal dollars,
  ampersands, quotes and angle brackets remain correct. Cover punctuation,
  malformed metadata, invalid schemes, control characters and oversized targets.
- **Lifecycle:** coalesced messages, wrapped labels, page boundaries, forward /
  back / refresh / quit, disabled paging, disconnect cleanup, and snoopers with
  different capabilities retain correct text and balanced links.
- **Negotiation:** enable, refusal, disable, re-enable, duplicate responses,
  fragmented negotiation and independent GMCP/MXP states; legacy browser and
  Telnet clients receive no new markup or duplicate output.
- **Transport:** preserve ordering under partial writes and backpressure, with
  and without MCCP. Validate copyover record compatibility and links after a
  supported hotboot on the original connection.
- **Browser:** commands use the normal input route, URLs use anchors, keyboard
  activation works, trigger behavior and split history are preserved, and bad
  presentation metadata falls back to the existing text renderer.
- **Cost:** one bounded scan of emitted text, bounded metadata, no database I/O,
  polling, or world traversal. Use the existing output benchmark facility to
  compare linked and ordinary output if the shared hot path changes materially.

Applicable existing server checks include:

```sh
python3 tests/async/test_ansi_runtime.py
python3 tests/async/test_word_output_style.py
python3 tests/async/test_word_output_integration.py
python3 tests/async/test_pager_contract.py
python3 tests/async/test_telnet_output_runtime.py
python3 tests/async/test_telnet_fragmentation_contract.py
python3 tests/async/test_gmcp_control_journey.py
python3 tests/async/test_websocket_runtime.py
python3 tests/async/test_copyover_evidence.py
./scripts/format.sh --check
make -C src
```

Run the narrow tests while developing and the applicable set at completion.
Add an executable help/link regression using the actual help renderer and
delivery path; source-text assertions alone do not prove the feature. Use the
existing local journey tooling for live help paging and hotboot, with isolated
development data and endpoints.

In the companion web worktree, run focused Vitest tests for the decoder,
segmentation and interactions, plus `pnpm --dir frontend type-check` and
`pnpm --dir frontend build`. Inspect browser output and exercise clicks in live
and history panes. Verify native MXP behavior in Mudlet (including the package's
declared 4.19.1 minimum when available) and MUSHclient; distinguish real-client
proof from serializer/harness proof. Missing client coverage is an explicit
remaining validation item, not a passing result.

Implementation is complete when both feature uses work through the real output
path, legacy peers remain compatible, and the acceptance cases have evidence.
Production deployment is a separate operation and is not part of this task.

## Implementation log and handoff

### Chunk 1: help during paging

Review: [PR #909](https://github.com/LuminariMUD/Duris/pull/909), commit
`731d44d1d`, labels `bug`, `enhancement`, `documentation`.

Implemented the prerequisite in `select_session_input()`: a full `help` command
at the head of an active playing session's input queue passes through the normal
playing-queue gates, releases the old page, and uses normal command dispatch.
Matching uses the existing case-insensitive argument parser. Other pager input,
abbreviations, editors and non-playing sessions retain their existing behavior.
No help-handler bypass or new input endpoint was added.

Extended the existing WebSocket/pager executable harness to cover typed and JSON
help, exact-once dispatch, queue order, case/whitespace, pager cleanup, action /
charm / creation / playing-queue gates, and editor/non-playing ownership.

Verified on 2026-11-09:

- `python3 tests/async/test_pager_contract.py` passed.
- `SANITIZE=1 python3 tests/async/test_pager_contract.py` passed (ASan/UBSan).
- `python3 tests/async/test_casting_input_queue_runtime.py` passed.
- `./scripts/format.sh --check` passed.
- `make -C src -j8` passed (MariaDB development build).

The harness executes production admission, queue selection, dispatch and pager
bodies with controlled world/transaction boundaries; it is not live-client proof.
Next: prove optional owned link metadata through send/accumulation/queue/pager,
then add transport serialization. The feature itself is not implemented yet.

### Chunk 2: output-link ownership and coordinates

Review: [PR #913](https://github.com/LuminariMUD/Duris/pull/913), implementation
commit `420a0c21f`, stacked on #909; labels `enhancement`, `bug`, `documentation`.

Implemented the lifecycle prerequisite on `branch/clickable-links-output`:

- `OutputContext::links` borrows producer byte ranges only until `send_to_char()`
  returns. The delivery boundary rebases them after styling and copies them into
  `txt_block::links` or the existing command accumulator's `command_links`.
- Queue nodes own optional `OutputLinks*`; plain input nodes leave it null.
  `write_linked_output()` reuses `write_to_q()` and rebases metadata when it
  coalesces. `get_linked_output()` moves metadata out before the existing
  `get_from_q()` releases it. Legacy dequeue and queue flushing also release it.
- `descriptor_data::showstr_links` owns ranges in `showstr_head`. Page slices
  clip/rebase the records and replay through normal sends with `LOG_NONE`.
  Quit, help replacement and disconnect use `free_paging_data()` for all owned
  pager storage. Copyover recovery still creates a zeroed descriptor; transport
  capability retention has not been implemented yet.
- `OutputLinkFrame` contains normalized `AnsiString` characters and distinct
  visible code-point link ranges ready for transport serialization. No wire tags
  are stored in queues, help prose or logs.
- Bounds: 64 links and 8,192 total target bytes per retained metadata set;
  command targets are currently limited to a single `help <topic>` under the
  existing input size limit, and URLs to HTTP/HTTPS with 2,048 target bytes.
  Invalid or excess metadata drops decoration while preserving the text.
- Plain sends avoid link parsing/allocation. Linked styling/fallback conversions
  use the existing `AnsiString` source-offset mapping. There is no registry,
  second queue, new input endpoint, or per-character retained metadata.

Executable integration coverage now includes producer lifetime, linked/unlinked
coalescing and separate blocks, style and whole-command budget fallback, Unicode
and dollar offsets, malformed targets/overlaps/limits, labels crossing pages,
refresh/back/forward/quit, disabled paging and owned cleanup. It exercises actual
production send/queue/pager bodies and the link module; it does not yet prove
client clicks, snoop link rendering, protocol negotiation or wire escaping.

Two defects exposed by those required paths were repaired: the pager counted
UTF-8 bytes and could split a code point, and a prior command's global pager
style-fallback flag could incorrectly mark later non-paged chat as `preserve`.
The chat regression forces a real crowded pager fallback before testing normal
say/tell/guild output. Input-queue test fixtures initialize the new optional field
to null; the normal input APIs and gates remain unchanged.

Remaining implementation: consume `get_linked_output()` in real transport output,
render snooped metadata for each snooper, implement MXP/GMCP-browser capability
and hotboot state, adopt help and URL producers, implement the companion DurisWeb
client, then complete all acceptance journeys and actual-client validation.
The framework prerequisite alone does not make any player output clickable.

Verified on 2026-11-09:

- `python3 tests/async/test_word_output_integration.py` and its `SANITIZE=1`
  ASan/UBSan run passed, including the new real lifecycle and chat regressions.
- `python3 tests/async/test_pager_contract.py` and its `SANITIZE=1` run passed.
- `test_casting_input_queue_runtime.py`, `test_casting_input_gate_runtime.py`,
  `test_transaction_input_queue.py`, `test_item_movement_input_queue.py`,
  `test_input_queue_reset.py`, `test_item_movement_prompt_runtime.py` and
  `test_spell_abort_command.py` passed under `tests/async/`.
- `test_ansi_runtime.py`, `test_word_output_style.py`,
  `test_telnet_output_runtime.py` and `test_websocket_runtime.py` passed under
  `tests/async/`.
- `./scripts/format.sh --check` and `make -C src -j8` passed.
- `OUTPUT_BENCHMARK=1 python3 tests/async/test_word_output_integration.py` passed.
  In this development harness, 12,800 messages to 64 recipients measured about
  0.58 microseconds CPU/message without metadata and 1.08 with two links and
  preserve styling; static styling plus links measured 3.04. Terminal byte counts
  were identical between the first two cases. These are local presentation
  measurements, not a live-server or transport performance claim.

Local evidence is under `bin/tests/phase1-output-{runtime,asan,build}.log`,
`bin/tests/phase1-output-benchmark.csv` and `bin/tests/phase1-websocket.log`;
generated artifacts are not committed. No production or database operation was
performed. Remaining acceptance checks listed above stay open until their
corresponding implementation exists.

### Chunk 3: MXP transport, snooping and retained state

Review: [PR #917](https://github.com/LuminariMUD/Duris/pull/917), implementation
commit `f9863457e`, stacked on #913; labels `enhancement`, `documentation`.

Implemented the native transport on `branch/clickable-links-mxp`:

- `net/mxp.*` owns the small negotiation state and native renderer. The greeting
  requests option 91 with `DO`; refusal tries `WILL` once. Both directions,
  unsolicited re-enable, repeated replies and disable are handled through the
  existing fragmented Telnet parser. MXP is independent of GMCP and suppressed
  on WebSockets.
- `process_output()` now consumes the owned metadata. Established MXP sessions
  render `SEND`/`A`; other peers continue through the existing terminal renderer.
  No new output queue or write transport was added.
- Generated tags briefly enter secure mode and immediately return to locked mode;
  literal labels never enter secure mode. Attribute escaping covers quotes,
  apostrophes and ampersands/angle brackets. Raw non-SGR escape controls are
  visualized, and remaining C0/C1 controls are defused (newline/tab retained).
  Command metadata also rejects MXP's `|` menu separator, ensuring one help
  command rather than a command menu.
- Links are closed/reopened on every newline and page. Decoration reaching the
  existing string limit falls back to the ordinary terminal representation.
  The dollar normalization precedes tags, so literal dollars in targets are not
  reinterpreted by a subsequent output pass.
- Snooping maps semantic spans through the existing `%` prefixes and CR removal;
  each snooper independently renders using its own MXP capability. Metadata
  remains outside logs and wire tags remain outside the queue/pager storage.
- Native copyover version 22 appends an enabled flag at byte 808, after the full
  version 20/21 record. Versions 12–21 retain their original widths and default
  off. The actual descriptor producer retains only established MXP, and recovery
  restores it on retained native connections; old/off peers negotiate before
  emitting tags. No schema migration or live operation was performed.
- The permanent contract is [docs/network/MXP.md](../network/MXP.md).

Verified on 2026-11-09:

- `python3 tests/async/test_word_output_integration.py` passed, including the
  actual output loop and sender/snooper capability matrix, escaped targets,
  locked literal/forged input, balanced line/page output, refresh and size fallback.
- Its `SANITIZE=1` run passed (ASan/UBSan).
- `python3 tests/async/test_telnet_output_runtime.py` passed with real parser /
  negotiation and linked bytes included in partial-write, TLS and MCCP cases.
- `test_copyover_evidence.py` passed with actual descriptor-producer checks,
  frozen historical record widths, invalid MXP-state rejection, and versions
  12–22; `test_telemetry_copyover_format.py` and `test_copyover_custody.py` passed.
- `test_item_movement_prompt_runtime.py`, `test_pager_contract.py`,
  `test_telnet_fragmentation_contract.py` and `test_ttype_runtime.py` passed.
- `make -C src -j8`, `./scripts/format.sh --check` and commit-time tidy passed.
- The extended output benchmark passed: native rendering of the same message
  measured approximately 0.93 microseconds CPU/message without links and 2.22
  with two preserve-styled links (12,800 messages / 64 recipients). Static
  styling plus native links measured 4.35. This is a local presentation fixture,
  not live-server capacity evidence.

Evidence: `bin/tests/phase1-mxp-{output,asan,build,copyover,custody}.log` and
`bin/tests/phase1-mxp-benchmark.csv`. The protocol observer checks wire modes and
visible text, not actual client behavior. Native-client clicks and an
original-socket hotboot with links remain open acceptance items.

Next: adopt real help references/search results and shared URL recognition, add
the negotiated browser presentation contract and chat URL coverage, implement
the companion DurisWeb client, then run the remaining live/client journeys.
This chunk renders explicit metadata correctly but has not yet converted the
real help/URL producers; ordinary help output is not clickable yet.

### Chunk 4: authored help references and search results

Review: [PR #921](https://github.com/LuminariMUD/Duris/pull/921), implementation
commit `b34e608ef`, stacked on #917; labels `enhancement`, `documentation`.

Implemented real help producers on `branch/clickable-links-help`:

- Existing `wiki_help(string)` / `wiki_help_single(string)` and prose consumers
  retain their interfaces. Explicit overloads return the same rendered text and
  optional owned link spans; only `do_help()` adopts executable help metadata.
- The authored-help parser converts valid `[[topic]]` references to the existing
  cyan label with the separate target `help topic`. It removes bold markers as
  before. Unclosed, empty, nested or unsafe references remain readable literal
  text. Arbitrary player output does not adopt wiki reference syntax.
- Search-result titles carry corresponding help targets; redirects, matching,
  missing topics, dynamic details and attribute-help dispatch reuse existing
  paths. No database access, cache rewrite, cooldown or new input route was added.
- The existing search can return 101 titles at up to 256 bytes each. Metadata
  bounds are now 128 records / 32,768 target bytes so every ordinary result fits,
  replacing the preliminary 64 / 8,192 bounds recorded in chunks 2–3. Per-record
  command and URL limits are unchanged. Larger exceptional metadata still loses
  decoration rather than visible text.
- Legal cached help pages can exceed a queue block. `do_help()` sends large
  output in at most 2,048-code-point chunks, using the existing `AnsiString`
  serializer and source-offset mapping to preserve attributes, UTF-8 and clipped
  target spans. Equal-attribute escaped-dollar pairs stay in the same block;
  generic terminals use their attribute-free dollar normalization. The behavior
  also works with paging disabled. This localized repair avoids changing the
  general queue API or building a second help-output pipeline.
- Permanent help authoring/runtime documentation and the MXP bounds are updated.

The extended output integration harness executes actual help lookup/render,
`do_help()`, styling, queue, pager and output-loop bodies. Its catalog is a
controlled in-memory boundary and dynamic class-detail generators are excluded
from ordinary-page cases. It proves valid/malformed references, Unicode targets,
search and redirects, all 101 maximum-width result targets, legacy fallback,
large Unicode output, dollar boundaries, attribute dispatch, and frozen paging
after a catalog edit. It does not yet prove an actual native-client click.

Validation evidence is recorded in `bin/tests/phase1-help-{output,asan,build}.log`
and `bin/tests/phase1-help-{spells,class}.log`. Normal and ASan/UBSan integration,
`make -C src -j8` and formatting checks passed. The help-cache, flat-file help
catalog, reported-latency, pager and native Telnet runtime checks also pass; the
cold real-help spell/class regressions retain their existing browser facts and
permissions. Commit-time formatting and tidy passed; the branch is pushed for
review.

Next: shared HTTP/HTTPS URL recognition (including literal query ampersands and
color transitions), negotiated browser text/chat presentation, DurisWeb rendering
and all remaining live/client journeys. In particular, inspect the existing
Duris markup interpretation of query parameters such as `&name`: URL recognition
must preserve the actual destination rather than accepting a color-stripped one.
Derive URL targets before help chunk/pager slicing so a bisected label retains
its complete destination; detecting a fresh URL from each delivered fragment
would incorrectly shorten the target. Do not join unrelated sends to infer one.
Help links now reach the real native output path; web URLs and browser links are
still incomplete. No production operation has occurred.

### Chunk 5: shared URL recognition and frozen destinations

Review: [PR #934](https://github.com/LuminariMUD/Duris/pull/934), implementation
commit `6b4afe897`, stacked on #921; labels `enhancement`, `documentation`.

Implemented on `branch/clickable-links-urls`:

- `output_links_with_urls()` uses shared lexical rules in `net/url_text.h` to
  recognize HTTP/HTTPS in visible Unicode text. It handles color changes,
  case-insensitive schemes, query/fragment text, dollar normalization, trailing
  punctuation and balanced delimiters. Explicit help spans take priority.
- `AnsiString` preserves URL parameter ampersands such as `&name=`, `&n=` and
  bare `&no-cache` flags that previously collided with color resets. Source
  offset maps remain correct. Normal color behavior outside URLs and existing
  literal-ampersand escaping are retained. The permanent MXP contract documents
  the deterministic lexical rules and ambiguous bare reset spelling.
- Output-only queue entry points now use `write_output()` to prepare a complete
  original send before coalescing. All production direct output writes in
  `comm.c` / `prompt.c` and `SEND_TO_Q` are adopted; input writes keep the existing
  queue API. The actual queue/transport is unchanged.
- `OutputContext::links_prepared` distinguishes new messages from frozen
  help chunks/pager replay. Already clipped or rejected destinations are never
  inferred again from fragments. Authored output preserves this provenance
  while resolving profiles. There is no cross-message URL accumulator or ID
  registry and no client-side regex or command inference.
- Literal URL ampersands are canonically escaped when slices need protection;
  ordinary output that needs no escaping keeps its bytes. Original text remains
  the logging source. News's existing bounded-page admission checks the actual
  canonical bytes so successful display still acknowledges the news.
- Two larger boundary cases required repairs: help chunks now map link bounds
  from the full page's source offsets rather than reparsing a partial URL;
  `AnsiString::ansi()` accepts the actual destination capacity so canonical
  escaping can exceed one queue block inside the existing command accumulator.
  Queue blocks still keep their normal limit, and help still emits bounded
  chunks. The canonicalizer's input is bounded below 64 KiB, with an allocated
  worst-case output bound; it does not silently truncate a larger canonical form.
- MXP percent-encodes non-ASCII UTF-8 URL target bytes before legacy CP437
  conversion. Targets survive while labels retain the existing terminal encoding.

Executable coverage includes exact target values, color changes within schemes,
Unicode/dollars, invalid schemes/empty authority, query and bare-flag ampersands,
balanced punctuation, no nested help links, legacy output, unrelated coalesced
sends, real announcements/help/news, oversized-target rejection, help pages above
64 KiB with URLs crossing chunks, canonical expansion above one queue block,
pager refresh and complete targets on every page, logging and authored-context
provenance. The Telnet harness also checks an actual CP437 write with a Unicode
URL destination. Shared output-only boundary stubs preserve existing focused
fixtures; the integration tests link the real scanner and output loop.

Evidence is under `bin/tests/phase1-urls-{output,asan,build,prompts,websocket,gmcp}.log`
and `bin/tests/phase1-urls-benchmark.csv`. The normal integration and focused ANSI,
style, cache, pager, news, latency, terminal-mode, shutdown, editor, numeric-input,
Telnet and WebSocket/GMCP runtime checks pass. Final ASan/UBSan integration,
`make -C src -j8` and `./scripts/format.sh --check` passed. The existing benchmark
passed: native URI rendering with two preserve-styled links measured about 3.13
microseconds CPU/message, versus 1.01 for its explicit plain baseline (12,800
messages / 64 recipients). Static styling plus native links measured 5.90.
Ordinary output with no URI retains its allocation counts. These are local
fixture measurements, not live capacity. Commit-time formatting and tidy passed;
the branch is pushed for review.

Remaining: negotiate the browser presentation capability, attach the same
semantic links to existing text/chat envelopes, implement and verify DurisWeb,
then perform native-client and original-socket hotboot journeys. No live-client
click, production operation or deployment has been performed. The goal remains
in progress even though help and URL producers now reach native MXP delivery.

### Chunk 6: negotiated browser text and chat presentation

Implemented on `branch/clickable-links-web-protocol`:

- Exact `Duris.Links 1` support through the existing Core.Supports parser and
  feature report. It needs no Subscribe stream. Removal, GMCP disable and the
  player's opt-out stop optional presentation. Existing support storage already
  retains the bit on supported native hotboot; no record-layout change is needed.
- One shared JSON formatter replaces the duplicated chat run/dollar serializer
  and supplies ordinary WebSocket text. Existing `type/category/data` remain;
  the same envelope carries optional `presentation` with literal text, colors
  and half-open code-point `{start,end,kind,target}` links. A flush produces one
  ordered text batch, preserving original block folding and leading newlines.
- Already queued WS wire bytes drain before raw text/prompt state is consumed.
  This reuses the existing queue/buffer and adds no second retry queue or matching
  IDs. Optional over-budget/invalid/allocation-failed presentation falls back to
  ordinary text. Packet size remains inside the existing WS output budget.
- All existing chat channels can carry optional `bodyPresentation`, built from
  the recipient-approved body, for their normal sender/body layout. Adopted
  full-line profile snapshots retain their fields and gain links when negotiated.
  No language/visibility transform or profile resolution is repeated. Existing
  unnegotiated payloads retain their shape and one-copy delivery.
- The complete capability report fits when all existing streams are supported
  and active. Shared legacy chat-root construction keeps required-field failures
  atomic; new snapshots are also atomic. The wire contract and structured-chat
  guide are updated.

Verified: normal and ASan/UBSan output integration, including one-envelope order,
Unicode offsets, literal text, capabilities/opt-out, full versus body chat, raw
queue retention under pressure and 150 allocation-failure points. The actual
GMCP parser/wire fixture passed under sanitizers with version negotiation,
Add/Remove/Set, no subscription, all chat entry points, all-stream reporting and
disable behavior. Deferred-prompt serialization and `make -C src -j8` passed.
The local benchmark covers new-capability chat (about 20–21 microseconds CPU per
message for both full/body snapshots, 12,800 messages to 64 recipients); this is
not a live capacity claim. Formatting and commit hooks remain required at commit.

Evidence: `bin/tests/phase1-web-protocol-{output,asan,gmcp,prompts,build}.log`,
`bin/tests/phase1-web-protocol-benchmark.csv`. The output harness exports real
synthetic producer payloads to `bin/tests/clickable-links-wire.json` when run with
`OUTPUT_PRESENTATION_FIXTURE=bin/tests/clickable-links-wire.json`; use these for
the paired browser qualification, not private player data.

Next: implement the client decoder, line slicing through triggers, store/history
retention and a shared safe renderer in the companion worktree. Preserve console
versus chat palette contracts and the existing sender/body fallback; use the
existing command sender for help and user-activated HTTP/HTTPS anchors. Validate
rendered browser clicks/keyboard/history and then native-client/hotboot journeys.
The frontend testing skill will use Playwright because the Browser plugin is
absent. Prepare website release news locally under the website skill; this PR-only
task does not publish the not-yet-deployed feature or refresh unrelated Mudlet
package history. The goal remains active until the entire Phase 1 acceptance
scope is proven.

## Scope review

Keep the shared representation because two transports and two real link types
need it. Keep queue/pager ownership, escaping, negotiation and hotboot work because
they are on the existing delivery path. Reuse the current color conventions,
help lookup and command sender. Omit speculative entity identities, registries,
menus, extra protocols and general output redesign. Recheck that every changed
file supports a Phase 1 requirement before implementation is submitted.
