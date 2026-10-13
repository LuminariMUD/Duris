# Native zone connection tracking

Status: proposed implementation plan; no server changes made.
Tracking issue: [#65 — Add native zone connection tracking and in-game reports](https://github.com/LuminariMUD/Duris/issues/65).
Source baseline: `d860af6e40a6c42a2f180a9a0f6d92c6a2c21de8`, inspected 2026-10-13.
Related work: [world placements and the Underdark connector, issue #37](https://github.com/LuminariMUD/Duris/issues/37).

## Outcome

Give builders an in-game report of which zones have connections, the exact room
endpoints, and how a player crossed each connection. Discover actual crossings at
`char_to_room()` regardless of whether movement came from an exit, portal, item,
spell, trigger, room proc, or mob proc. Keep observations across restarts.

Implement this inside the existing server: one connection module, the existing
`zcheck` command, and the existing persistence writer. No operator scripts,
external collectors, new service, database, or telemetry dependency.

The report combines **current exits** with **observed travel**, keeping their
meaning distinct. An exit exists without necessarily being usable. An observation
proves that a crossing happened under some circumstances, not that everyone can
repeat it now. A zone with neither is **no known connection**, not disconnected.

### Non-goals

- Automatically prove every possible route through arbitrary C++ or scripts.
- Build a pathfinder, solve keys/quests/character requirements, or promise safe
  entry and return. This feature reports directed connections and evidence.
- Parse every area/proc into a second world model or maintain hand-authored route
  declarations. Unused dynamic routes remain undiscovered.
- Change movement behavior, relocate areas, or implement issue #37's placements.
- Store individual player histories, raw command text, chat, or credentials.

## Existing code to reuse

| Evidence | Consequence for this design |
| --- | --- |
| [`char_from_room()` and `char_to_room()`](../../src/world/handler.c) unlink and insert characters; departure writes the previous room vnum to `specials.was_in_room`. | Observe the existing movement boundary. The inspected direct `in_room` assignments outside it do not implement ordinary player travel. |
| [`char_to_room()`](../../src/world/handler.c) inserts the character before running room/mob entry effects, which may move or extract it and cause a false return. | Record insertion before those effects. Testing the function's final return value would lose real crossings. |
| [`zcheck`](../../src/world/zcheck.c) already scans the loaded world and has builder permissions and paging. Its walk starts inside a zone when no entrance exists. | Add a connections subcommand; do not interpret the existing audit as proof of external access. |
| [`special()`](../../src/cmd/interp.c) knows the object, mob, or room being dispatched; [`studioproc`](../../src/mob/studioproc.c) knows target vnum, event, and trigger index. | Capture this information at shared dispatch points instead of editing every compiled proc. |
| [`check_item_teleport()`](../../src/magic/magic.c), [`proclibobj_transporter()`](../../src/mob/studioproclib.c), and [`portal_general_internal()`](../../src/specs/specs.object.c) resolve actual objects and destinations. | Add object identity at these common adapters; preserve random destinations as observed outcomes. |
| [`show_map_at()`](../../src/world/world_quest.c), `do_at()` in [`actwiz.c`](../../src/cmd/actwiz.c), and `guildwindow()` and the boat `look_out` branch in [`specs.object.c`](../../src/specs/specs.object.c) temporarily move characters for viewing. | A raw count of `char_to_room()` calls would manufacture connections. These operations need explicit suppression. |
| [`runtime_flags`](../../src/core/structs.h) and the [`CHAR_RFLAG_*` definitions](../../src/core/defines.h) already hold transient character state. | One additional flag can distinguish a fresh departure from an old saved `was_in_room`, without changing character layout or save formats. |
| [`persistence_writer_submit()`](../../src/player/player_save_worker.h) accepts a captured callback, and [`flatfile_atomic_write()`](../../src/flatfile/flatfile_store.h) publishes files atomically. | Reuse them for a server-owned diagnostic snapshot in both persistence backends. |

## Builder interface

Extend `zcheck`; keep its existing forms and output working:

```text
zcheck links                 connections for the current zone
zcheck links <zone#>         connections for an exact zone vnum
zcheck links all             one summary row per loaded zone
```

The new form uses exact zone vnums, not a fallback to a table index. Reuse the
existing immortal access and pager. All three forms are read-only.

A zone report shows inbound and outbound connections with source/destination
zone numbers and names, room vnums, mechanism, and evidence:

| Evidence | Display |
| --- | --- |
| Current exit | Direction, door keyword, current closed/locked/secret/blocked flags; explicitly not a traversal guarantee. |
| Observed crossing | Mechanism/caller, command verb when known, relevant object/mob/room vnum or trigger identity, count, first seen, and last seen. |
| Historical observation | Loaded from a previous run and not observed in this run; still useful evidence, not current validation. |
| Stale endpoint | A recorded room is missing or belongs to a different zone now; keep the record visible but do not count it as a current connection. |

Show a separate reverse-direction entry only when there is evidence for it. If
none exists, say **return route not established**, not **one-way trap**.
Show distinct mechanisms between the same endpoints separately. The all-zones
summary includes zones with no known inbound or outbound connection, observation
coverage/capacity, and snapshot status. Scan the loaded exits once for the whole
summary, not once per zone. Page deterministic results without silently dropping
rows; a shortened summary directs builders to the per-zone report.

Do not merge different entrances into an invented through-route. Recording
`A -> B` and `B -> C` does not prove one player can travel from A to C.

## Capture and attribution

### 1. Record actual placement once

Add a small `src/world/zone_connections.c` and `.h` module. Its table is owned by
the game thread and contains directed cross-zone observations, not every step.

- After `char_from_room()` has actually unlinked a character and written
  `was_in_room`, set one transient departure flag. A vetoed departure must not
  set it.
- In `char_to_room()`, consume that flag and capture the source vnum by value.
  Require a valid fresh departure and valid, different source/destination zones.
  Do not treat a saved `was_in_room` as evidence, and do not resolve a missing
  origin through `real_room0()`'s fallback.
- Record immediately after room-list insertion and `ch->in_room = room`, before
  look, rider movement, room procs, or other entry effects. No later dereference
  of this character is needed by the recorder.
- A blocked or rejected placement creates no row. Invalid-destination recovery
  into limbo creates no row. Same-room and same-zone moves create no row.
- For `A -> B -> C` caused by an entry proc, retain both actual crossings and
  their respective causes, even if the outer `char_to_room()` returns false.
  Reaching a lethal room is still an arrival; the report promises no survival.
- Admit mortal PCs, including a linkdead PC moved by gameplay. NPCs and staff
  characters do not establish player routes. Login/recovery placement, temporary
  viewing, and staff relocation of a mortal are excluded.

Consume/reset the departure flag on rejection, restoration, and lifecycle paths
so it cannot leak into a later placement. It is runtime state only: never save
or restore it in player or copyover data. Verify allocation/reuse initializes it.

### 2. Get a caller for every crossing without a proc registry

Add a defaulted C++20 `std::source_location` argument to `char_to_room()`.
Existing three-argument production calls continue to compile and automatically
supply the calling file, function, and line. This identifies an otherwise
unclassified native movement path without a stack trace, symbol lookup, or
changes to hundreds of procs. Update declarations and affected harness stubs;
do not add a second movement implementation or a macro wrapper.

Use function and repository-relative file as stable mechanism information.
Keep the last observed line for diagnosis, not as part of the connection key:
unrelated source edits must not create duplicate routes. Historical locations
describe the code that ran then and may need lookup after later source edits.

Add one small scoped context, confined to this feature, for information the
immediate caller cannot supply. It saves/restores its previous value so nested
dispatch does not overwrite the outer cause. It carries only copied IDs,
bounded labels, command verb, and a suppression flag; never borrowed character
or object pointers in retained records.

| Hook | Information supplied |
| --- | --- |
| Recognized command dispatch, before `special()` and item teleport checks | Command verb and whether this execution is an administrative operation. Do not use `desc->last_command`: it is confirmation state, not a reliable movement cause. |
| `special()` and room/mob entry callbacks in `handler.c` | Target type and vnum of the proc being invoked. |
| `studioproc` firing | Target type/vnum, existing trigger index, event, and configured keyword when relevant. This works for periodic, death, and other non-command triggers too. |
| Generic item teleport, object transporter, and portal adapters | Resolved object vnum and configured activation keyword, plus the native caller. |
| Normal movement and shared ferry/transport/ship entry points | Confirmed exit direction or transport identity and action. Do not infer walking merely from `dir >= 0`; other callers pass those values too. |
| Temporary viewing and administrative placement paths | Suppress collection across the entire operation, including nested calls and the return placement. Suppression is inherited and cannot be cleared by an inner context. |

A native proc without richer context still records its actual caller. Display
that fact as `native: <function>` instead of guessing a portal, spell, or exit.
This is a useful explanation of how the crossing occurred, not a promise of a
complete player walkthrough. Known object/script metadata supplies the more
useful activation detail. Do not persist arbitrary command arguments or speech;
script keywords come from the matched trigger definition.

Context ends with its dispatch. Delayed movement must use the executing
callback's caller and available event/entity data, not an earlier player's
command. Retain attribution for followers/riders as an explicit inherited cause
when the central insertion recursively places them.

Audit all existing temporary-placement pairs while implementing suppression.
Known viewing sites above are the starting set, not a claim that the list is
exhaustive. Do not suppress all negative direction values: real portals and
falling use them. Suppress direct administrative actions at their functions as
well as command dispatch, since game code can call them directly.

### 3. Keep the table small and honest

Key observations by source/destination zone and room vnums plus the mechanism
identity: caller, meaningful direction/command, and available entity/trigger
identity. Repeated crossings update a saturating count and timestamps. Use an
in-memory lookup; no per-movement file writes, SQL, world scans, or backtraces.

Keep current exits out of the stored table. Read them from `world[]` when a
builder asks, so resets and scripts that alter exits are reflected immediately.
An observed dynamic route does not become a permanent ordinary exit.

Use a compile-time cap of 65,536 observation rows and bounded text fields as the
initial implementation limit. Measure the actual footprint before completion.
When full, continue updating known rows, count refused new observations, and
show **coverage incomplete: capacity reached**. Do not silently evict evidence
or turn missing rows into a negative connectivity claim. This needs no new
configuration surface.

For transport, distinguish boarding, travel, and leaving. Ship passengers can
remain inside the same interior room while the ship changes map location;
`char_to_room()` observes their room changes, not each sea square sailed.
Record actual boarding/disembarking endpoints and the available vehicle
identity. Mark reusable/generated room endpoints as transient; do not restore
them as current links merely because the same numeric room slot exists again.
Such observations remain historical after restart. Combining separate trips
through an interior must not imply a permanent passage between their ports.

## Persistence and lifecycle

Observations are diagnostic state. Memory remains authoritative, following
[ADR 0002](../adr/0002-persistence-reset-memory-is-the-authority.md).

- Store one versioned snapshot at `runtime/zone-connections/state`. Create and
  validate its private directory at boot using the existing filesystem
  conventions; `flatfile_atomic_write()` requires ownership by the server user
  and no group/other permissions. Add the runtime directory to `.gitignore`.
- Use this same file in MariaDB and flat-file builds. It is not a second player
  persistence backend. Do not use `persistence_mode_flatfile_root()` here:
  that root is absent in MariaDB mode. No migration or SQL table is needed.
- Load at boot. Absence starts an empty table. Validate version, sizes, IDs,
  counts, and timestamps before publishing a loaded table; a malformed file
  remains intact and produces a visible unavailable-persistence status. Keep
  collecting in memory, but do not overwrite that file automatically.
- At the existing recurring persistence phase, capture a dirty table at most
  once per 60 seconds. Send the owned snapshot to the existing writer, where
  serialization and atomic file replacement occur. No mutable game pointers
  reach that thread.
- Add one `zone_connections` persistence job kind and a completion branch in
  `player_save_pipeline.c`. Use the captured generation as the job's owner ID,
  so the existing completion identifies exactly which snapshot finished without
  changing the writer's completion format. At most one snapshot is outstanding
  during play. A successful completion marks only that generation saved; new
  observations during a write stay dirty.
- A write failure is terminal for that job and leaves memory dirty for the next
  scheduled attempt. Never put a failing diagnostic write in the writer's
  retry-at-head loop. Report status through `zcheck links` and existing logging.
- Queue a final capture before the existing clean shutdown/copyover drain. If
  an older capture is outstanding, allow one final queued snapshot behind it;
  process completions in order without losing later dirty data. Reuse the
  existing drain and deadline; add no feature-specific shutdown veto or wait.
- A crash can lose observations newer than the last successful snapshot.
  Normally that is up to the 60-second cadence plus writer backlog; during a
  persistence failure it can be longer. Show last successful save and dirty
  status instead of claiming a guaranteed crash window.
- All restored observations start historical. Missing or reassigned endpoints
  are flagged; room/zone vnums are stored instead of process-local indexes.
  No stored row asserts that a proc, item, or entrance is still available.

## Files and implementation sequence

Implement as one coherent server feature. These are work steps, not independent
services or a requirement to split it across releases.

| Step | Files and work | Proof before moving on |
| --- | --- | --- |
| 1. Capture and identity | New `src/world/zone_connections.{c,h}`; `src/world/handler.c`; `src/core/prototypes.h`, `src/core/defines.h`; `src/Makefile`; affected test declarations/stubs. Add automatic caller capture and the transient departure flag. | Real production insertion/departure code records crossings once, handles nested relocation, and cannot use a stale origin. No movement behavior changes. |
| 2. Explain and filter | `src/cmd/interp.c`, `src/cmd/actmove.c`, `src/mob/studioproc.c`, `src/mob/studioproclib.c`, shared portal/transport code; scoped suppression in the identified viewing/admin functions. | An exit, item portal, scripted transfer, compiled proc, and transport produce distinguishable explanations; temporary/admin placements do not. |
| 3. Persist | Existing boot/recurring/shutdown paths in `src/world/db.c` and `src/net/comm.c`; copyover capture before its existing drain; `src/player/player_save_worker.{c,h}`, `src/player/player_save_pipeline.c`; `.gitignore`. Keep feature serialization in the one new module and reuse `flatfile_store`. | Restart/copyover restore evidence, pending snapshots preserve capture order, and file errors do not block gameplay or starve player saves. Both backend builds work. |
| 4. Report and document | `src/world/zcheck.c`, `lib/information/help_index`; focused tests in `tests/async/`; update the data lifecycle/reference documentation with the implemented behavior. | Authorized builders can inspect incoming/outgoing routes and unknown coverage in-game; existing `zcheck` syntax and read-only behavior remain intact. |

Use the exact touched callers found during implementation; do not bulk-edit
every `specs.*` file. The shared declaration change requires compatible harness
stubs, not a rewrite of the movement tests. Keep this plan updated with actual
files and validation results as implementation proceeds.

## Proof required for implementation

Extend relevant existing tests before adding harnesses. Where current tests only
inspect source text, add executable coverage of the production boundary; do not
prove capture solely by calling the new table's insert helper.

1. **Movement boundary:** cross-zone versus same-zone; failed departure and
   rejected insertion; invalid-destination recovery; login/recovery without a
   fresh departure; nested `A -> B -> C`; arrival followed by death/extraction;
   rider/follower placement; reused character storage.
2. **Mechanisms:** ordinary exit; a fixed and a random item portal; object
   transporter; command and periodic script transfers; compiled room and mob
   procs; a travel spell; ferry movement and ship boarding/disembarking. Check
   source/target rooms, cause, and available entity/trigger identity. Include a
   previously unannotated native caller to prove automatic caller coverage.
3. **False evidence:** quest-map view, guild window, boat look-out, `do_at`,
   staff relocation of a mortal, and staff/NPC travel create no player-route
   rows. Nested contexts restore attribution and cannot cancel suppression.
   Real negative-direction travel still records. A stale confirmation command
   cannot appear as the cause of a later periodic move.
4. **Reports:** a zone with no known entrance remains unknown; reverse travel
   is independent; alternate mechanisms remain separate; current locked/blocked
   exits are labelled accurately; changed exit targets appear immediately;
   historical/stale/transient endpoints cannot masquerade as current proof.
   Check exact zone lookup, permissions, paging, and existing `zcheck` behavior.
5. **Persistence:** round-trip, absent/corrupt/truncated files, atomic-write
   failure, dirty updates during a pending save, final capture behind a pending
   save, clean reboot, copyover, and a crash after a known checkpoint. Test in
   isolated runtime directories and with the existing writer, not only a codec.
6. **Cost and capacity:** repeat a crossing and show row count stays constant;
   exercise saturation and its coverage warning; measure collection and
   snapshot-capture costs on the loaded world. No I/O or whole-world scans in
   movement. Check `links all` performs one world scan and stays within the
   existing game-loop latency budget. If it does not, bound report/capture work
   across existing pulses before acceptance; do not add a worker or silent
   output truncation.

Run the focused tests for this feature and the affected movement/proc/writer
paths, including the existing `test_zcheck_contract.py`,
`test_movement_liveness_runtime.py`, `test_studioproc_command_movement_contract.py`,
`test_proclib_bridge_contract.py`, and `test_player_save_worker.py`.
Run `./scripts/format.sh --check`, `make -C src`, and the applicable completion
gates from [TESTING.md](../guides/TESTING.md): `make test-all` and the isolated
`make test-db` gate for the shared writer/lifecycle integration. Qualify both
supported persistence builds. No production operation or CI wait is required.

Finish with an isolated development gameplay journey: use a mortal to cross
representative exit, portal, and script routes, inspect `zcheck links` as staff,
then reboot/copyover and inspect the saved evidence. Capture a baseline report
for issue #37's candidate zones without assuming their intended destinations or
changing world content. Tests may use the repository's existing Python journey
drivers; operating the feature must require only the server and its commands.

## Ablation decisions

| Decision | Reason |
| --- | --- |
| Keep the central placement hook and fresh-departure flag. | Needed to cover unknown mechanisms while rejecting saved origins and failed moves. Existing runtime flags avoid character/save-layout changes. |
| Keep automatic caller capture plus a small scoped context. | The caller explains previously unknown native travel; the context supplies object/script identities and prevents known false observations. Neither requires a proc registry. |
| Keep one native snapshot and one existing-writer job kind. | Evidence must survive restarts. A distinct job kind provides ownership and completion routing without borrowing another domain's key or creating another worker. |
| Reuse `zcheck` and the loaded exits. | Meets the in-game reporting requirement without another command registration, API, dashboard, or world parser. |
| Drop static extraction of every portal, reset, script, and compiled proc. | Actual crossings are already observable centrally. Complete static discovery is a different, much larger problem. The report exposes the resulting coverage limit. |
| Drop route declarations, per-player trails, prerequisite solving, graph/pathfinding libraries, external telemetry/rollups, new SQL schema, and configuration knobs. | None is needed to report direct zone connections and the mechanism actually observed. |

Implementation is complete when collection, explanation, exclusions, persistence,
and the in-game report satisfy the checks above with no operational side script.
It need not claim the world has been exhaustively explored to be useful and
correct about the evidence it holds.
