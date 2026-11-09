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
- Current implementation branch: `branch/clickable-links-output`, stacked on
  `branch/clickable-links-phase1`.
- Worktree: `/home/aiwithapex/projects/duris-worktrees/clickable-links-phase1`.
- Plan: `docs/ongoing-projects/clickable-links-phase1.md` in that worktree.
- Deliver focused, reviewable commits and PRs as each chunk is verified. Stack
  dependent changes and keep this document current for handoff.
- Implementation will also need a companion branch/worktree in `durisweb` for
  its player renderer and transport decoder. Create that during implementation,
  after reading that repository's instructions. Keep commits in their owning
  repositories and link the server and client changes.
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

## Scope review

Keep the shared representation because two transports and two real link types
need it. Keep queue/pager ownership, escaping, negotiation and hotboot work because
they are on the existing delivery path. Reuse the current color conventions,
help lookup and command sender. Omit speculative entity identities, registries,
menus, extra protocols and general output redesign. Recheck that every changed
file supports a Phase 1 requirement before implementation is submitted.
