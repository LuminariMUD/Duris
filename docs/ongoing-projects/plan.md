# Issue #498: GMCP state and command-result contracts

Status: **control/time, lifecycle and combat ready in PRs #542/#544/#545/#546; owner items in progress**. Updated 2026-11-01.

- Server work: [Duris #498](https://github.com/LuminariMUD/Duris/issues/498).
- Client adoption and real-Mudlet qualification: [duris-client #26](https://github.com/LuminariMUD/duris-client/issues/26).
- Server branch: [branch/issue-498-gmcp-contracts](https://github.com/LuminariMUD/Duris/tree/branch/issue-498-gmcp-contracts), natively linked to #498 in GitHub Development.
- Local worktree: /home/aiwithapex/projects/duris-issue-498.
- Audited runtime baseline: ee6f9fbf344b3828c896d0ba032128c43b0b9f9d (merged master; reviewed in branch head `94bc675ee`).
- Original planning baseline: 2b2b6fb2d578b88e54b2a653506c4dd429346479; retained only for change comparison and historical test evidence.
- Client reference: [immutable investigation](https://github.com/LuminariMUD/duris-client/blob/aa40a50cda789525dddddcce6f8056e53985a0bb/docs/ongoing-projects/protocol-interface-investigation.md), checked alongside both current issue bodies.

The previous contents of this path are already preserved byte-for-byte in
[plan-issue-420.md](plan-issue-420.md); comparison was performed before editing.
The original planning commit supplied the plan only. Estimates concern future work.

## Master integration - 2026-11-01

Merged `origin/master` at `ee6f9fbf3` into this issue worktree. Runtime and
test sources matched that master exactly; implementation had not started.
The only conflict was the shared plan path. This file retains the complete
#498 plan; master's complete #500 handoff is preserved byte-for-byte in
[plan-issue-500.md](plan-issue-500.md).

Re-audited the original-to-merged-master delta against the current owning
source and both live issue bodies on 2026-11-01. The findings and line numbers
below describe `ee6f9fbf3`. At that review the seven core contracts were unimplemented;
upstream changes affect session admission, durable item/reward publication,
container access, command gates and the workload baseline. The implementation
steps and proof below account for those changes without adding new streams.

Merge validation passed: `make -C src -j4`; the GUI GMCP contract, prompt
regression and input-receipt tests; game-loop phase and WebSocket protocol
source contracts; staged formatting and whitespace checks; and both plans'
relative links. No booted-game or real-Mudlet qualification is claimed by this
merge. The implementation and measurement requirements below remain pending.

Local analysis tooling: the merge's normal hook passed with clang-tidy 18
explicitly selecting `--gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13`, the
build compiler's installation. Its automatic GCC 16 header selection failed.
The ignored `CLANG_TIDY` wrapper changes tooling only; checks remain enabled.

## Implementation progress - 2026-11-01

- Applied-damage slice (qualified for review): Duris.Combat 1 requires explicit support and
  interest; active consumers receive each outgoing applied hit in the existing
  FIFO and no duplicate legacy round. Damage uses the actual before/after HP
  delta after gameplay caps/conversion, including secondary victims. Per-delivery
  message metadata carries spell/physical kind and the existing melee/archery
  critical result; unprovided critical is null. Copies at the damage boundary
  prevent nested spell procs changing the caller's metadata. No gameplay RNG call.
  Events carry context/process/generation/body revision and string sequence.
  Each interval permits 64 events/64 KiB including conservative envelope reserve;
  allocation, queue or budget failure invalidates the connection rather than
  silently dropping history. State retains its separate coalescing/retry behavior.
  The native ASan/UBSan event cases pass actual fractional HP conversion,
  secondary/primary identity, masked labels, source metadata delivery copies,
  known/unknown critical, FIFO count/sequence, both bounds, 45 allocation budgets,
  queue failure, 64-bit sequence and disabled construction on both transports.
  Both builds, physical-layer/death-result/missile regressions, prompt/phase/docs
  checks and 2,386,264 sanitizer fuzz executions pass. The booted journey passes
  subscribed physical damage with a known critical boolean, no duplicate legacy
  round, and matching current context/process/generation/body identifiers.
- PR #545's fuzz harness now supplies the viewer helpers used by combat state.
  Its isolated link failure was reproduced, repaired and qualified with 1,389,773
  sanitizer fuzz executions, then pushed separately as `49fc1cf25`.

- Combat state slice: extend legacy Combat.Update with authoritative room-local
  target/tank, explicit nulls, viewer masking and accepted-output revisions.
  The mutation audit found direct HP writes across regeneration, affects,
  spells, scripts, equipment and commands; dozens of new mutation hooks would
  still miss setters in content code. Instead, the existing descriptor flush
  samples exactly the two current prompt subjects and compares bounded scalar/
  name snapshots. It constructs JSON only for changed state; disabled/pre-entry
  recipients do not resolve names or construct output. No room/population scan,
  new periodic traversal, retained character pointer or observer index is added.
  This replaces the proposed dirty-room mechanism while preserving its outcomes.
  Native ASan/UBSan passes independent HP, masking, non-GMCP healing/posture,
  rescue, room departure, freed-subject safety, identity reuse, bounded names,
  unchanged JSON-allocation counts and allocation/transport retries on both
  framing variants. The booted wire journey passes real combat against an NPC
  fighting a non-GMCP NPC tank, ally extraction/tank null and foe extraction/
  both nulls. MariaDB and client-free builds, prompt, loop-phase and documentation
  checks pass. Legacy applied-hit rounds remain compatible; the next dependent
  chunk must add negotiated applied-damage events and metadata/ordering bounds.

- Lifecycle is ready for review in [PR #544](https://github.com/LuminariMUD/Duris/pull/544),
  based on PR #542. Implementation `243562574` plus parent integration
  `fe9477140` is published. Both server builds, sanitizer/native lifetime and
  allocation/queue cases, live Telnet/WebSocket A/account/B/failed-entry/body
  switch/reconnect, and original-socket uncompressed/MCCP copyover pass.
- Combat state is ready for review in [PR #545](https://github.com/LuminariMUD/Duris/pull/545),
  based on PR #544; implementation `1424da65b` is published and mergeable.
- Applied damage is ready for review in [PR #546](https://github.com/LuminariMUD/Duris/pull/546),
  based on PR #545; implementation `5898ce013` plus parent integration `08ff013a9`
  is published. Server, sanitizer, booted wire and fuzz qualifications pass.
- Current implementation branch: branch/issue-498-owner-items, based on PR #546.
  The next focused PR targets branch/issue-498-combat-events. Implement bounded,
  subscribed owner inventory/equipment snapshots and real mutation/publication
  ownership; audit durable rewards/restoration before adding item notifications.
  Remaining inventory, actions/results, client/real-Mudlet and matched overhead
  gates are still required. No issue completion or HP-symptom fix is claimed.
- PR #544 review fix: a Session-aware player switching into an ordinary NPC now
  receives the compatible bootstrap after its body revision. The native regression
  fails on the reviewed guard and passes with player-owned NPCs admitted; the
  live switch journey also requires Vitals, Affects and Room.Info before return.
  Uncontrolled NPCs remain excluded from player bootstrap.

- PR #542 review fix: capability invalidation remains pending until accepted
  by the transport, including duplicate support-removal requests in one burst
  and further requests while its queue retry is pending. The real parser/send
  regression fails on the reviewed code and passes with the sticky pending flag
  on both framing variants. Session work remains on its dependent branch.
- Completed lifecycle implementation branch: branch/issue-498-session-lifecycle, based on
  the published PR #542 head. Session work will target that immediate parent.
  Implement connection-scoped context/generation and account/chargen/playing
  snapshots; observe semantic entry and invalidate before terminal release.
  Repeated negotiation must retain the generation, and morph/switch must retain
  the owning player's identity. No authentication, persistence or replay redesign.
  Extend the native and booted wire journeys for real transition/order proof.
  Native ASan/UBSan cases now cover stable entry keys, chargen cancellation,
  same-socket replacement/clear ordering, morph/switch body revisions, 40 JSON
  allocation-failure points, control-before-data retry and copyover adoption.
  Copyover version 18 extends the existing descriptor record with optional
  connection support/interest/context/generation and receipt continuity; versions
  12-17 retain their frozen 660-byte prefix. A process marker resets snapshot
  revision baselines after hotboot while the entry key stays unchanged.
  No new persistence service or additional copyover file is introduced.
  MariaDB and client-free builds pass. The booted journey verifies initial
  account/chargen/playing state, repeated negotiation/preferences, A/account/B,
  new-connection context, failed entry and live NPC switch/return. Copyover
  native evidence/custody and actual original-socket exec checks pass; process
  markers also scope Time revisions for consumers that do not use Session.
  The parent PR review fix is published as `a82e52dd8` and retained here.
- A clean detached `881853d21` reference checkout and checksummed MariaDB binary
  are now prepared under `bin/qualification/issue498/baseline-881/` for matched
  measurements. No feature code or player data was copied into that reference.
- Review stack root: [PR #542](https://github.com/LuminariMUD/Duris/pull/542),
  branch/issue-498-gmcp-contracts. Control/time commit `998a1639b` is published;
  dependent chunks will use their own branches and target their immediate parent.
- Master advanced to `881853d21` during qualification (quest replacement policy
  and diagnostics). It merged cleanly. Both builds, the production GMCP harness and the updated quest-target
  regression passed before merge `44a13bc1d` was published.
  The initial `ee6f9fbf3` artifacts stay historical; matched final overhead must
  use the updated upstream baseline to avoid attributing quest-policy changes
  to the protocol work.
- First review chunk (ready for review): bounded Core.Supports.Set/Add/Remove, Capabilities and
  explicit Subscribe, plus the shared cached Duris.Time stream. The existing
  GUI harness now runs the real parser/control/send paths and additional time/
  preference/flood/retry cases over both transport variants. Native GUI,
  prompt, input-receipt, periodic-event and minimal-boot regressions pass.
- MariaDB and client-free flatfile builds pass. The new booted
  test_gmcp_control_journey.py passes normal Telnet/WebSocket dispatch, entry,
  account return/re-entry, reconnect, preference off/on, invalid preference,
  negative staff hours and day-phase changes. A WebSocket decoded-string edge
  found by that journey was fixed by sharing the bounded control application
  path before the legacy reserialization adapter; both transports now enforce
  the same module/size/count/rate rules.
- Initial 30-second ASan/UBSan GMCP fuzzing passed 12,487,256 executions; the
  expanded raw/decoded-envelope recheck passed 3,213,603 executions. Ten new
  retained seeds cover both forms. The final-source replay passed another 2,519,725 executions. Real-Mudlet/client
  coordination and matched overhead measurements remain open.
- Preserved the unmodified `ee6f9fbf3` binary, SHA-256, compiler/machine metadata
  and deterministic 17-frame/11-package fixtures (4,716 JSON payload bytes)
  under ignored `bin/qualification/issue498/baseline/`. These are baseline
  artifacts, not booted workload or percentile/performance qualification.
- Capability/subscription and Time v1 shapes are in
  [GMCP.md](../network/GMCP.md). Only implemented contracts are advertised.
  Session lifecycle is the next dependent chunk; combat, inventory, actions,
  command results and final matched measurements/client qualification remain.
  No #498 completion or HP-symptom fix is claimed by this first slice.

## Outcome

Deliver all seven server contract areas in #498: authoritative combat/tank
state; game time; session lifecycle; capability/subscription gating; owner
inventory/equipment; semantic action/activity/cooldown events; and authorized
scan, ship-scan, dice, identify and WHO results. Preserve gameplay decisions,
recipient information policy, legacy streams and bounded game-loop work.
Record a disposition for every additional candidate. Supply real serialized
fixtures and measured costs so client #26 can adopt each advertised feature.

Each core contract needs executable proof through its real gameplay/session
path. A declared package, helper test, unchanged hash or screenshot alone does
not establish the outcome. The player/pet/opponent HP symptom remains an
investigation until reproduced and verified in the client.

## Non-goals

- Client UI/automation rewrites, releases and text-fallback removal belong to
  #26. Server fixtures, coordinated scenarios and evidence handoff remain
  required here; server tests alone cannot claim client qualification.
- No replacement command dispatcher, remote action API, event broker, durable
  replay, database schema, synchronous storage calls, population feed, world
  traversal per hit, zone-graph service or additional map generation.
- No per-second countdown packets, recursive inventory push, speculative item
  deltas, generic observer framework or blanket export of hidden affects.
- No production operation, deployment, unrelated cleanup, full burn-in or wait
  for hosted CI. Keep text behavior available during the companion migration.

## Findings from the owning source

Paths and line numbers refer to merged master `ee6f9fbf3`. Changed owners were
re-read; 22 unchanged protocol/gameplay/reference files were also compared
byte-for-byte with the original planning baseline. The issues and client
investigation are inputs, not proof of implementation.

1. **Negotiation/bootstrap already exist.**
   [gmcp.c](../../src/net/gmcp.c):58-86,125-237,286-307 handles DO/DONT,
   deferred snapshots, Core.Hello, Client.Info and opt-in Char.Input. It does
   not handle Core.Supports or gameplay requests. Bootstrap already sends ship
   clears, status, vitals, affects, group, room, quest and combat.
   [gmcp.h](../../src/net/gmcp.h):139-144 distinguishes negotiated transport
   from the character's NOGMCP preference. Pre-character lifecycle/control needs
   a descriptor policy without bypassing that preference for gameplay data.

2. **WebSockets share the bootstrap.**
   [account.c](../../src/account/account.c):2296,
   [nanny.c](../../src/account/nanny.c):2215,
   [actoth.c](../../src/cmd/actoth.c):5811-5814 and
   [ws_handlers.c](../../src/net/ws_handlers.c):1057-1068 reach the same sender.
   Account/nanny have several direct state and character assignments, including
   pre-entry cancellation and switched originals. No protocol session generation
   exists. Hook semantic boundaries; do not increment generation from bootstrap
   or mechanically replace every STATE assignment. Account recovery now
   acknowledges successful resets only after durable storage through account.c's
   account_apply_recovered_password() and ws_handlers.c's ws_complete_reset_reply();
   reset_completed is not a
   character attachment. Preserve writer_wait_id/descriptor-liveness handling
   and same-account session closure. build_account_load_request() also refuses
   character admission while that account's chest purchase is pending.

3. **Combat is immediate and attacker-centric.**
   gmcp.c:1013-1108 creates target/optional round, no tank; end sends target:null.
   The target serializer uses GET_NAME without recipient masking there.
   [prompt.c](../../src/net/prompt.c):299-342 derives tank as the opponent's
   opponent, requires both relationships to be local, and masks an unseen tank
   as "someone". [fight.c](../../src/combat/fight.c):5752-5759 sends victim
   vitals and attacker target/round; secondary-target damage can omit the round,
   and metadata is "unknown"/false. set_fighting(), unlink_fighting(),
   stop_fighting(), terminal extraction and update_pos() are distinct paths.
   Current packets do not prove ally damage, non-GMCP tank health or all posture
   changes stay fresh. Self HP already has its own Char.Vitals source.

4. **Time has small mutation boundaries.**
   [weather.c](../../src/world/weather.c):75-99 advances time_info.hour and the
   calendar; astral_clock_setMapModifiers() owns hourly map/announcement rules.
   [actinf.c](../../src/cmd/actinf.c):6995-7104 contains staff "time N" and the
   ordinary do_time() path that can schedule autoreboot. The field is hour,
   not hours. Publish after normalized mutation; serialization must only read.

5. **Item dirtiness exists but is not subscription state.**
   [handler.c](../../src/world/handler.c):1873-2193,3051 onward owns core item
   transfers/equip and sets runtime flags. obj_to_char_at_end() is a separate
   append/restoration path. unequip_char() has a saving argument.
   [files.c](../../src/core/files.c):1455-1465 clears persistence dirty flags
   and temporarily unequips on terminal saves. GMCP cannot depend on those
   flags surviving saves. [structs.h](../../src/core/structs.h):500 already
   has obj_uid; vnums are templates. [utils.h](../../src/core/utils.h):612-613
   allows staff 3,000 carried objects: list bounds are a real requirement.
   do_inventory(), do_equipment(), get_equipment_list(), list_obj_to_char()
   and show_obj_to_char() own visibility, anatomy, duplicate presentation and
   wraithform policy; raw object fields do not automatically preserve it.
   Upstream get/put/look/examine/empty now enforce
   locker_container_access_allowed(); LockerMovementAudit admission can refuse
   movement or MakeScrap() before mutation. Preserve those boundaries and the
   non-takeable private-chest policy in item_command_policy.c.
   [sql.c](../../src/sql/sql.c):233 onward owns world_quest_publish_reward():
   a reward can remain detached after its durable save, then hydrate/attach or
   restore for a live actor, or leave durable custody for later login. The
   committed callback in [player_save_pipeline.c](../../src/player/player_save_pipeline.c):531-575
   may retry after actor departure. Protocol dirtiness belongs to completed
   live publication, not reward creation, save admission or an internal counter.

6. **Completion owners already know useful outcomes.**
   do_bash()/do_rescue() delegate to bash()/rescue() in
   [actoff.c](../../src/cmd/actoff.c); rescue resolves and retargets around
   8210-8300, with CharWait afterward.
   [memorize.c](../../src/classes/memorize.c):490-568,1097-1253 distinguishes
   completion and voluntary/disrupted cancellation.
   [bard.c](../../src/classes/bard.c):1918-1928 knows actual song completion;
   [epic_skills.c](../../src/classes/epic_skills.c):1252 onward owns infusion;
   [mining.c](../../src/economy/mining.c):286,385,802 separates command and
   delayed results. [events.c](../../src/world/events.c):368 onward owns
   CharWait; [affects.c](../../src/magic/affects.c):1938-1960 creates hidden
   short affects. [json_utils.c](../../src/core/json_utils.c):1009-1074 excludes
   AFFTYPE_NOSHOW and already exports visible duration seconds. Reuse those
   owners instead of input labels/output matching or exposing internal tags.

7. **Requested results can reuse existing decisions.**
   actinf.c:9792-10064 performs scan detection/RNG and temporary room traversal.
   do_who():7444 onward filters by level, morph, trust, faction, anonymity,
   host and displayed fields/counts.
   [tradeskill.c](../../src/economy/tradeskill.c):2546-2608 holds actual dice
   results inside the roll loop. [ship_combat.c](../../src/ships/ship_combat.c):196
   onward authorizes scan_target() by contacts/range before armor/internal
   output. [magic.c](../../src/magic/magic.c):10499 onward gates identify,
   including NOIDENTIFY/effective-level differences. Shop, auction, crafting
   and spell callers reach it with different authority.

8. **Flush names are not construction/measurement guarantees.**
   gmcp.c:660-728 shares contact payloads by vessel/verification variant but
   builds personalized own-ship info before hashing.
   [comm.c](../../src/net/comm.c):2327-2388 still flushes GMCP first, then
   runs durable completions and save publication. Its "gmcp_flush" span includes
   the new chest/combat-outcome/frag-cap pulse work alongside existing account
   recovery, saves and caches. sql_async_pulse() runs after that span and can
   publish further changes. Count protocol work at construction/delivery sites;
   mutations after the state flush must remain dirty for the next flush.
   [latency_trace.h](../../src/persistence/latency_trace.h) has bounded
   count/total/max/top samples, not a full percentile distribution.
   [GAME_LOOP_PHASES.md](../network/GAME_LOOP_PHASES.md) fixes phase ordering;
   do not move output/persistence/combat owners to make protocol tests pass.

9. **Not every proposed stream exists, and several need no duplicate.**
   Char.Items/Char.Skills appear only as package constants; source search found
   no callers of json_build_stat_roll()/json_build_chargen_complete(). Ship
   details, quest map/status, affect seconds, chat presentation and input
   receipts already work. [epic.c](../../src/world/epic.c):1950-1975 has cached
   text with a cache-miss generation path; displayed_alignment() enforces
   disclosure delay. [public-population.md](../guides/public-population.md)
   explains why public MSSP/live population is withheld. A new stream must not
   revive it or add periodic report generation.
   Existing Quest.Status now normalizes killCount during pending reward/history
   stages in json_utils.c:1225-1242; world_quest_start_reward() temporarily reuses
   quest_kill_how_many for money. Preserve that serializer instead of exporting
   raw quest fields. gmcp_quest_status()/gmcp_quest_map() retain availability,
   paid-map and completion clears; reuse the current geographic policy without
   another eligibility traversal or new quest stream.

## Contract decisions and bounds

Finalize schemas in docs/network/GMCP.md (new), with examples produced by
executable serializers. Duris.* names below are proposals, not current APIs.
Record agreed fields/version availability in both trackers before client
fallback retirement. This is coordination, not a new approval ceremony.

- Preserve legacy packages/default sends. New catalogs/events require compatible
  support and explicit interest; WebSockets keep their legacy default without
  automatically subscribing to new large lists. Additive combat fields remain
  compatible with existing readers.
- Implement bounded Core.Supports.Set/Add/Remove for a small fixed feature set,
  not a generic registry. Unknown modules/versions never grant authority.
  Proposed Duris.Capabilities advertises only working schemas and effective
  stream state; proposed Duris.Subscribe controls interest in new streams.
  Support means decodable; interest means currently wanted. Unsubscribe clears
  pending protocol work, stops construction and explicitly invalidates client
  state.
- Gate before JSON/list work: negotiation, effective preference, support,
  interest, then dirty/request state. Session/Capabilities control remains
  available to capable negotiated clients to report preference disable/enable;
  gameplay streaming still honors NOGMCP.
- Use a connection-local character generation and monotonic revisions/event
  sequences, encoded losslessly where needed. Advance generation at semantic
  attachment/entry, not renegotiation/bootstrap. A new connection starts a new
  context. Session has account/chargen/playing states and character:null;
  never expose credentials/account identifiers.
- State replaces its documented whole scope. Define omitted versus null;
  target:null/tank:null clear combat, items:[] is authoritative empty, and
  unavailable/ineligible differs from empty. Session invalidation clears all
  prior character streams. State resync never replays historical action events.
- Events carry generation, event sequence, kind/outcome, permitted actor/target
  and small known reason codes. Preserve each actual event in order; do not
  coalesce it like state. No replay/exactly-once promise across disconnect.
  Char.Input remains only a dequeue receipt. Never include typed arguments,
  account recovery secrets or chest credentials in these payloads.
- Time v1 carries hour 0-23 and phase: dawn 04-08, day 09-15, dusk 16-18,
  night 19-03. Optional calendar indexing/year offset must be specified if
  retained. Cooldowns use monotonic server milliseconds and remaining
  milliseconds at emission, scoped to the connection; clients count locally.
  Keep global wait, selected skill cooldowns and status/activity restrictions
  separate; a deadline alone does not guarantee CAN_ACT.
- Initial limits to validate: Supports <=8 KiB/64 entries/96 bytes per entry;
  new read/subscription requests burst 2 then 1/second per family; result pages
  <=128 rows/16 KiB; new semantic events <=64 events/64 KiB per descriptor per
  flush interval; new replaceable-state/list output <=32 KiB per descriptor
  per flush plus a shared round-robin work budget. Event bytes use their
  separate quota and enter the existing FIFO at completion, without waiting
  for the state flush. These are implementation constants, not new user
  options. Bound strings/collections before construction and final encoded size.
- Reuse existing bounded Telnet/WebSocket FIFOs and failure/close behavior,
  avoiding a second event queue. Events are never silently overwritten;
  exhausting event/transport limits uses the documented overflow/connection
  reset policy. Preserve control-message room when transport permits final
  invalidation. Test it: state resync cannot reconstruct missed dice/history.
- Large item/WHO/scan results use bounded pages with revision, continuation and
  complete semantics; ordinary lists fit one page. Replace only completed
  revisions, never a silently truncated list. Invalidate item-state continuations
  on owner, visibility or mutation changes. Requested command results retain
  values captured during their authorized pass; pagination must not repeat a
  scan, random decision or identification. Cancel old-character pending pages/
  snapshots on session change and suppress late event construction for that
  generation. Already queued output stays in FIFO order before the session
  boundary; never cancel durable gameplay transactions or their offline
  recovery. Completion delivery must match the current character/generation,
  with a fresh snapshot on later entry. No borrowed item pointers survive
  extraction; construction, captured results and pending protocol work must
  also have explicit total bounds.

## Implementation sequence, files and proof

Each step is a reviewable commit or small related series. Extend existing
harnesses before adding focused tests; do not build another test framework.
Advertise a feature only after its real path works.

### 1. Baseline, contracts and gating (2-3 active hours)

- Freeze serialized fixtures, seeds, populations and workloads at `ee6f9fbf3`,
  not the original planning revision; record construction counts, bytes and
  latency before runtime changes. Recapture the existing Quest.Status fixtures
  with pending rewards/history represented through the current serializer.
- For booted tests use the maintained disposable backend authority/setup helpers
  (test_flight_network_journey.authority and run_world_quest_dual_backend.setup_run_root).
  Honor current migration/runtime manifests, including SQL migrations 0056/0057
  where applicable. Startup now requires successful frag_cap_runtime_boot(),
  including minimal worlds; do not bypass it or add a second fixture bootstrap.
  This is local/dev qualification setup, not new migration or production work.
- Add narrow support/interest/control state in src/net/gmcp.c/h and
  src/core/structs.h; initialize/free/reset it on descriptor creation/close/
  recovery. No new persistent preference/configuration service.
- Integrate bounded state flushing at the existing cadence without moving
  output/persistence/combat phases. Async mutations published after an earlier
  flush remain pending for the next one.
- Proof: production input/send paths for Set/Add/Remove, malformed/oversized
  inputs, unknown versions, request floods, legacy Telnet/WebSocket defaults,
  preferences and unverified identity. Extend the existing GMCP fuzz corpus
  where parser branches are added.

### 2. Session and time (2-3 active hours)

- Hook attach/detach/account/chargen/playing in account.c, nanny.c, comm.c,
  ws_handlers.c and actual quit/return/switch paths. Audit failed load,
  pre-entry cancel, link-dead reconnect, copyover, morph and switched originals.
  Send invalidation before character pointers are released. Preserve existing
  chest-access invalidation in close_socket() and writer/account admission
  gates. Hook actual attachment/completion, not an accepted load/reset request;
  password-reset completion stays in account state until ordinary login.
- Bootstrap order: capabilities/effective streams, session boundary, then
  compatible snapshots. Same-socket detach sends character:null before new
  character data. Re-enable resends state without advancing entry generation;
  disable control is sent before gameplay gating blocks updates.
- Cache one small global time payload per revision. Invalidate after
  event_another_hour() normalization and staff time mutation. Entry/re-enable
  sends the current revision to interested recipients, without command calls.
- Defer optional calendar expansion/shutdown countdown metadata; neither is
  needed for the required clock/phase UI. Do not advertise them.
- Proof: initial/late negotiation, repeated DO, re-enable, A -> account -> B,
  failed attach, chest-purchase admission refusal, chargen cancel, reconnect/
  copyover, morph/switch identity and phase boundaries. Include a disconnect or
  account replacement while recovery/publication is pending: no late packet
  enters another character's generation and durable work still completes.
  Retain the existing account-recovery contract/native tests and extend the
  disposable recovery journey only where new lifecycle assertions need it.
  Assert serialization never calls do_time/shutdown/storage.

### 3. Combat, observers and damage events (3-5 active hours)

- Extend Combat.Update with tank and explicit target/tank nulls. Follow prompt
  relationships/locality and recipient PERS/visibility policy, including generic
  unseen identity. Keep self HP separate from target/tank percent/condition.
- Coalesce viewer state in the existing descriptor flush by sampling only its
  two current room-local prompt subjects. Compare bounded scalar/name snapshots
  before allocating JSON. This covers direct healing/regen/posture assignments,
  rescue, flee, death, departure and extraction, including non-GMCP tanks.
  The source audit found direct HP writes in events.c, affects.c, magic.c,
  class skills, commands and many specs; a new hook set would not be complete.
  Do not scan rooms/population/combat lists per hit or add an observer index.
- Resolve current relationships at flush, retaining only scalar/opaque runtime
  identity/name values between flushes. Never retain a raw victim pointer.
  Session/body changes invalidate the cache; accepted FIFO output advances the
  revision. Define the separate event ordering in the next dependent slice.
- Separate outgoing applied-damage events from replaceable target state.
  Preserve actually applied amounts, including secondary targets, without
  retargeting the primary enemy. Pass known damage-type/critical metadata from
  authoritative calculations; retain explicit unknown when unavailable.
  Never recompute/roll again. Document legacy round scope and prevent capable
  clients counting both old/new representations. No full miss/damage log.
- Files: gmcp.c/h, fight.c, handler.c and concrete health/posture owners found
  by the audit; keep any helper local to this responsibility.
- Proof: player/pet/enemy independently near death; masked names; ally and
  secondary damage; rescue/tank swaps; posture/heal; flee/death/departure/
  extraction; clear-before-reuse; unchanged RNG; no disabled construction.
  Under #26, identify the affected widget and verify values/labels/critical
  styling and delayed text before claiming the reported HP symptom fixed.

### 4. Owner inventory/equipment (4-6 active hours)

- Implement Char.Items.List inv/eq with generation, location, revision,
  completion, visible description, quantity, worn slot, usable selector and
  known condition/flags. Per-instance rows with quantity 1 are sufficient for
  separate objects; preserve duplicate targeting. Optional capacity/count/
  weight reuses existing values, never identification-only fields.
- Start with complete snapshots/empty or unavailable states. Revision-scoped
  entry tokens/selectors suffice for v1. If client agreement requires stable
  cross-snapshot identity, reuse audited obj_uid lifetime as an opaque string
  scoped to generation; no new allocator, vnum, raw pointer or rounded number.
- Add independent GMCP pending revision/dirtiness; saves may clear persistence
  flags. Cover transfer/append/restore, equip/unequip, extraction, containers,
  rename, damage/repair and visibility/anatomy/wraithform changes. Mark both
  owners on transfer, not only player command sites.
- Coalesce completed operations. Respect saving=true and restoration; never
  publish transient terminal-save unequips or partial get-all. Audit src/item
  transaction publication plus core/files.c and persistence restoration; emit
  after authoritative commit/publication, not speculative ownership changes.
  Include sql.c's world_quest_publish_reward(), player-save committed callbacks
  and reward restoration. A durable reward is not visible inventory until live
  attachment finishes; offline completion must not target the departed socket.
  Do not call the reward publication helper or read its repository to serialize.
- Serialize subscribed dirty/requested top-level lists with bounded pages/work.
  Nested contents remain explicitly requested with current owner, visibility
  and normal container-access eligibility, including the current locker gate.
  Invalidate pending pages if access changes. Owner lists do not become a
  private-chest contents API; no recursive push, polling or deltas.
- Files: gmcp.c/h, json_utils.c/h, handler.c, sql.c, player_save_pipeline.c,
  necessary item/publication owners and actinf.c presentation policy. Share a
  read-only presentation helper only if text/JSON truly share policy; do not
  invoke a printing command to serialize.
- Proof: empties, 3,000-item staff lists, duplicates/selectors, get/drop/give/
  get-all, wear/remove/disarm, containers, rename/repair, visibility, save/load,
  async success/failure/replay, extraction between pages and unsubscribe.
  Cover deferred quest reward attachment/reconstruction, logout before its
  publication and exactly one visible inventory revision after retry; refused
  chest access/audit/scrapping must not invent a mutation or expose contents.
  Extend the existing committed-reward publication and SQL chest regression/
  lifecycle harnesses for these paths. Verify ordinary inventory/reward restore
  on MariaDB and flatfile; private chests remain SQL-only.
  Assert one completed bulk revision and no extra persistence or hidden data.

### 5. Actions, activity, cooldowns and notices (5-8 active hours)

- Hook actual success/failure/completion/cancellation: bash/rescue/flee in
  actoff.c; disarm/consent in actnew.c and fight.c; follow/group in their cmd
  owners; study/prayer in classes/memorize.c; infusion in epic_skills.c;
  songs in bard.c; mining in economy/mining.c. Include early refusals and
  deferred/async completion for pending actions, not only the command wrapper.
- Send successful flee direction after movement succeeds, or explicit failure/
  cancellation. Publish only reasons already known/permitted to the recipient.
- Publish self global-wait and allowlisted skill cooldown changes from
  CharWait/event_wait and short-affect add/replace/remove/expiry in events.c
  and affects.c. Derive intervals from actual scheduled state, including
  restored timers. No hidden-tag dump or timer added solely to tick a UI.
- Send a small activity snapshot at entry/re-enable/change, with started,
  completed/cancelled and known stop reason. Separate studies/prayers/infusion/
  song cause from posture. Full prepared-spell catalogs are unnecessary.
- Inventory actual active client automation notice triggers. Include consent,
  follow/group, mining and skill-up notices. For tracks, frost beacon, scrying,
  spell-hit reports and arrival/trap/movement notices, reuse already-permitted
  values at existing recipient branches for active #26 needs; record every
  trigger's owner/event or an explicit client-accepted deferral. Do not replace
  "other notices" with a generic text-to-event parser.
- Eligible local rescue/assist observers receive small relationship/outcome
  updates, including required observed attack/miss transitions. No second
  room-wide combat log, remote feed or other players' cooldowns.
- Proof: success/refusal/failed roll, async finish, interruption/voluntary cancel,
  cooldown replace/expire/clear, command/skill variants, duplicate events and
  no false completion from affect loss. Verify bystander masking, a non-GMCP
  actor and multiple individual events before one coalesced state flush.

### 6. Authorized command results (3-5 active hours)

- First emit negotiated JSON alongside the existing authorized command.
  No GMCP handler directly calls gameplay functions. Any later transport
  request must enqueue the same command through normal wait/eligibility/
  input rules, with bounded pending request state. Preserve comm.c's current
  get_playing_cmd_from_q() transaction/chest gate, shared-bank reservations and
  account writer waits; a new request must not skip them as a "read-only" shortcut.
- Player scan: collect actual successful detections, including "here",
  directions/distances and explicit empty/failure, inside the existing pass.
  Restore ch->in_room before delivery. Preserve visibility/RNG count and order;
  do not re-evaluate detection for JSON.
- Ship scan: serialize already-authorized scan_target armor/internal/relative
  results separately from routine contacts. Retain bridge/range/contact rules
  and withhold world coordinates from unverified connections.
- Dice: emit the loop's actual result, sides, index/count and roll ID to the
  same allowed self/local observers, with recipient masking. No reroll; the
  capability/ID contract and client tests prevent dual-source processing.
- Identify: accumulate only fields actually revealed at successful spell/
  service branches after existing cost/authority/completion. Test NOIDENTIFY
  and effective-level differences, including shop/auction/crafting callers.
- WHO: serialize accepted rows and branch-specific displayed fields from
  do_who(), preserving filter/sort, explicit empty/failure, anonymity, trust,
  level and population privacy. Do not export internal totals/opposing names
  merely because the server knows them. No automatic roster.
- Files: actinf.c, tradeskill.c, ship_combat.c, magic.c, necessary service
  completion callers and gmcp.c/h/read-only serializers.
- Proof: text/protocol permitted-field parity, fixed RNG call counts, blocked/
  empty results, hidden targets, anonymous/trusted WHO, level-one/morph refusal,
  identify cost/failure and ship verification. Exercise normal input dispatch.

### 7. Integration, measurements and closeout (5-8 active hours)

- Extend test_gui_gmcp_contract.py/native harness for real serializers,
  Telnet/WebSocket send paths, new bootstrap and clears. Extend the prompt/
  toggle and input-receipt tests where their contracts change. Add focused
  native mutation/command journeys for uncovered gameplay requirements only.
- Implementation checks: ./scripts/format.sh --check, make -C src, the three
  focused GMCP tests, relevant new gameplay/persistence tests,
  test_game_loop_phase_contract.py and applicable public-population/output/
  command-queue tests. Register new regressions if runner discovery needs it.
  Reuse test_world_quest_reward_publication.py, test_private_chest_regressions.py,
  test_private_chest_lifecycle.py and test_account_recovery_contract.py where
  their publication/lifecycle owners are touched; extend their real-path proof
  instead of introducing a general notification or persistence test framework.
  Retain test_item_movement_input_queue.py/test_transaction_input_queue.py for
  any new request dispatch. These are implementation checks, not claims that
  this plan review ran gameplay journeys. All compiled artifacts remain under bin/.
- Cover initial/late negotiation, repeated bootstrap, reconnect/copyover,
  same-socket switches, disable/re-enable, support/interest changes, null/empty,
  stale revisions/duplicate events, slow consumers/overflow, legacy and
  unverified clients. Preserve bought/valid quest-map and ship privacy rules.
- In the actual client checkout run:

      python3 scripts/capture_server_gmcp.py --server /home/aiwithapex/projects/duris-issue-498

  Check that extraction covers the changed functions; commit fixture provenance
  on the client branch. Run affected real-Mudlet server-wire, connections,
  information, combat, time, split, ship and lifecycle scenarios. Inspect
  screenshots, numeric state and styling. Unavailable environments/scenarios
  remain explicitly unverified; native fixture success is not Mudlet proof.
- Finalize protocol/availability/compatibility/measured-limit docs and candidate
  dispositions; update docs/reference/CODEBASE.md only where navigation needs
  it. Link delivered commits/PRs and evidence in both issues. Keep unfinished
  external qualification explicit; do not close on serializer-only coverage.

## Measured overhead gate

Use merged-master `ee6f9fbf3` as the before baseline, with existing loop timing/
trace tooling and workload runners. Match frag-cap round/deadline state and
pending/retrying transactions as well as population/commands in each pair;
original-planning timings would omit newly landed game-loop work.
Add narrow protocol construction/send counters and a qualification workload
where missing, not a new observability service or synchronous logging.

- Match population, seed, commands/events, world fixtures, verification and
  ship/item distribution before/after. Also compare interest disabled/enabled.
- Workloads: idle/negotiation churn; combat with non-GMCP tanks, multiple
  observers and ally damage; unchanged/changing bridge observers; bulk items/
  large inventories; WHO/scan bursts; throttled/nonreading consumers. Include
  ordinary load and declared stress at 100 descriptors/3,000 carried items.
- Warm up, then run at least three matched pairs per workload with enough
  pulse samples for meaningful p99. Record sample counts/measurement overhead.
  Compute p50/p95/p99 from bounded raw samples or the existing suitable
  collector outside the loop; trace count/total/max summaries are insufficient.
- Report serializer calls, bytes/payloads, dirty/coalesced work, refused
  requests, sequence gaps/overflows, queue peaks, CPU/RSS and event-loop
  p50/p95/p99/max/overruns. Attribute protocol construction/delivery separately
  from the old gmcp_flush persistence/cache span.
- Proposed initial budget: <=5% pulse-p99 regression at matched representative
  load, pulse p99 <=250 ms, no additional attributable pulse overruns, and
  added GMCP work p99 <=2 ms/max <=10 ms per flush at supported workload.
  Idle/uninterested new-list construction, persistent backlog growth and new
  blocking storage calls must be zero. These are proposed limits, not measured
  results or owner agreement. Record the accepted budget in both trackers
  before final qualification; adjust batching/implementation with evidence
  instead of silently weakening the gate.
- Retain compiler/build, machine, seeds, sizes, revisions and raw artifact
  locations. Local results do not establish production overhead.

## Further-candidate dispositions

These decisions satisfy the requested assessment; all seven core areas above
remain in scope. Record reasons and later changes in both issues at closeout.
Do not advertise deferred features or remove their client fallback.

- Affect category/polarity and permitted expiry/removal reason: defer category
  tables/reason plumbing. Existing duration seconds permit local countdowns;
  loss is not proof of expiry. A mixed/unknown taxonomy needs a real consumer
  and policy audit. Selected self cooldown/activity state stays in step 5.
- Richer score: defer. Current STATS already uses vitals/status; redundant
  score queries are client work. A full score catalog needs another mutation
  audit without a present panel requirement.
- Learned skill list/changes: defer the full Char.Skills list (no active skills
  tab); retain actual skill-up notices in step 5. Do not advertise the constant.
- Spell preparation/activity: implement current activity/start/finish/cancel
  in step 5; defer full prepared-spell catalogs.
- Cached/delayed epic-zone report: defer. Existing cache/text generation and
  delayed completion/alignment disclosure need a separate prepared structured
  publication design. No new synchronous Redis work or immediate disclosures.
- Local weather/visibility/map mode: defer richer weather; reuse Room.Map and
  Room.Info. Add a scalar map-mode only if an active #26 ambiguity survives
  those packets, using already-resolved state, without another map calculation.
- Chat direction/recipient/event identity: defer broad schema changes; reuse
  presentation/timestamps and single-source routing. If an active consumer
  still needs "You -> Name" parsing, follow up with only permitted direction/
  recipient at existing chat construction, with its own contract/proof.
- Permitted chargen feedback: implement lifecycle here; defer roll/completion
  payloads until fields/disclosure policy and a client scenario are explicit.
  Unused builders do not authorize their precision. Account/chargen transitions
  remain required in step 2.

## Ablation review

Kept the seven core contracts, recipient-policy repairs on touched paths,
bounds, lifecycle correctness and real-path/performance proof: each serves an
issue requirement. Simplified requests to output from authorized commands and
reused bootstrap, socket FIFOs, room-local dirtiness, actual RNG values and
existing cooldown/event owners.

Dropped speculative deltas, a second command API, generic subscription/observer/
event frameworks, durable replay, periodic catalogs, optional shutdown/calendar
fields and catalogs without current consumers. Item paging stays because
staff can really carry 3,000 items; independent pending state stays because
saves clear persistence flags. No feature is justified by a constant alone.
The post-merge review keeps those decisions and reuses upstream admission,
publication, custody and recovery paths; it adds no parallel transaction owner,
notification framework, chest stream or frag-cap feature.

## Planning validation and my implementation estimate

Original planning checks on `2b2b6fb2d` (2026-10-30):

- python3 tests/async/test_gui_gmcp_contract.py — PASS; production serializers,
  wire/send/bootstrap/bridge fixtures with substituted world services.
- python3 tests/async/test_gmcp_prompt_regressions.py — PASS; native toggle
  matrix/source contracts, not a live prompt/gameplay journey.
- python3 tests/async/test_gmcp_input_receipts.py — PASS; native ASan/UBSan
  dequeue/sequence/privacy checks.
- Existing plan versus plan-issue-420.md — identical before replacement.

The original planning commit changed no C/C++ and did not qualify a booted
game, new contract, overhead comparison or real Mudlet. The later merge's build
and focused baseline checks are recorded above. This post-merge review changes
only this plan; it reuses those results because runtime/test sources are still
identical to `ee6f9fbf3`. Review checks passed for current source anchors,
relative links and named test paths, preserved scope/bounds and `git diff --check`.
Those checks validate this document, not implementation. All new-contract
gameplay/client/performance deliverables remain pending.

My estimate as implementing agent is **24-38 active working hours**, including
focused gameplay tests, fixture/scenario coordination, measurement and docs.
The step estimates sum to that range; the first contract/lifecycle/time/combat
slice is **7-11 hours**. That is roughly 3-5 focused eight-hour days, not a
delivery promise or a human-team estimate.

Assumptions: usable local/dev gameplay and Mudlet environments, no gameplay
policy redesign. External review/contract feedback or unavailable environments
add elapsed time. Unreproduced HP behavior, broader notices or missing mutation
hooks could raise this to **40-50 active hours**; update this plan with that
evidence if discovered. Client UI adoption/releases have a separate estimate
under #26.
