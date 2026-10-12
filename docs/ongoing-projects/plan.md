# Flight network implementation plan

Extend the existing flight service so each character can discover ordinary map stops,
travel between learned stops at distance-based fares, and earn discovery EXP. Keep
dedicated epic-zone trips separate, with their existing origins, fares, restrictions,
and one-way service.

Status: PR #51 review repairs and local qualification complete.
Updated 2026-10-12. The initial feature was qualified at `11354ecd1`.
This plan covers the complete feature in
[issue #40](https://github.com/LuminariMUD/Duris/issues/40).

## Review handoff

[PR #51](https://github.com/LuminariMUD/Duris/pull/51) contains the complete feature
on `feature/40-flight-network`, based on master `0da9292ca`. All six implementation
steps remain implemented. The subsequent review identified two flight regressions
and an older equipment-removal use-after-free; the repairs and new evidence are
recorded below.

- User decisions: 25 ordinary stops, exact 500-copper-per-room fares, and discovery
  EXP `current gain cap * count / 27` with normal racial, rested and difficulty
  modifiers. The two epic-only departures are excluded; bits 0 and 12 are reserved.
- One status mask stores discovery with EXP. Migration `0038_learned_flight_stops`
  is additive/rerunnable; snapshot schema 8 reads versions 1/3/5/7 with zero
  discoveries. Pwipes clear the field even on retained inactive player rows.
- The corrected catalog prepares 603 paths once per boot, using one BFS per
  origin. Shared list/buy selection, endpoint tickets and redemption checks keep
  discovery and epic access consistent. Existing movement and recovery are reused.
- Review repairs: failed payment cannot issue a ticket; a busy carrier cannot take
  a ticket through ordinary give; the zone/map lookup checks an invalid exit before
  dereferencing it. Native ASan/UBSan checks include these cases and wrapped paths.
- Sign 420, shared FLIGHTS help, command attributes and recovery documentation are
  updated. Existing visibility and loose-coin carrying rules remain: the journeys
  supply light/detect invisibility and carry a small purse. All seven named dragons
  remain killable and leave their normal corpses.

Verification on 2026-10-12:

| Check | Result |
| --- | --- |
| `make test-all -j16 TEST_JOBS=8` | 720 passed, zero failures/timeouts/signals; 539.50 seconds. Includes development and production builds and the full flat-file journey. |
| `make test-db` | 73 passed; 361 seconds. Includes the new MariaDB journey, immutable migration/legacy replay, and supported engine/runtime checks. |
| `./scripts/format.sh --all --check` | Full-tree formatting passed; subsequent touched-line checks and commit hooks passed too. |
| `make -C src pfile -j16` and `make -C migrations/tools all affects pfile_converter -j16` | Maintained auxiliary binaries built successfully. |
| `npm ci --prefix site && npm test --prefix site` | 15 tests passed. |
| `scripts/check_tests_catch.sh b79c08eef 11354ecd10bc` | Flight command and full-world journey tests pass on the implementation and fail before the validation/guidance fixes. Four maintenance checks pass on both; no control failures. |
| `python3 tests/async/test_player_item_snapshot_codec.py` (final audit) | ASan/UBSan: real checksummed files containing versions 1/3/5/7 load through the flat-file reader with an unsigned zero discovery mask. |

Both full-world backend journeys prove all 25 discoveries, exact 19.5p payment for
the 39-room Ugta–Kimordril route, occupied and empty-return copyovers, both restricted
epic trips, crash recovery, normal relogging, and the seven named-dragon corpses.
All five MariaDB boots found 603 available routes, prepared in 483–645 ms. The tested
MariaDB binary SHA-256 is
`51ff1e66ecd0d90cb02deb213fcbbaf324997e590163693c76efa6cea9629111`.
The full server journeys use ordinary development builds; sanitizers cover the native
command/recovery fixtures. No production migration, deployment or release tag was made.

The [regression record](../testing/REGRESSIONS.md#learned-flight-network) describes
coverage and the existing mechanics preserved during verification. The PR review
repairs below supersede the initial qualification for those paths.
Production rollout remains separate.

## PR #51 review repairs (2026-10-12)

All three findings in the [review](https://github.com/LuminariMUD/Duris/pull/51#pullrequestreview-5492994949)
were valid and are addressed in `69065e32f` and `68b638d9e`:

- Empty return events no longer link to the former passenger. Each return step
  schedules with a null victim; recovery already chooses a null rider for an
  unoccupied carrier. The real-server journey quits immediately after landing and
  verifies that the carrier returns home and resumes service without reconciliation.
- Ordinary `give` identifies a carrier by its flight procedure and calls the
  existing ticket validator even when that procedure is skipped. Readiness includes awake/mobile
  checks. The journey applies `MINOR_PARA`, verifies the flag, checks that the paid
  ticket and wallet remain with the player, then clears paralysis and flies.
- The older crumbleloot removal defect is fixed separately: item effects are
  removed before transfer can destroy the object, and an explicit extracted result
  protects single/all removal and automatic replacement. Shared robe cleanup
  replaces the two copies that previously dereferenced the item after transfer.
  The public removal regression reproduces the original heap-use-after-free under
  ASan/UBSan and covers ordinary items and trusted-player exemptions as well.

No new persistence fields, event types or inventory-transfer API were needed.
The branch already contains master `0da9292ca`; the review fixes remain separate
commits, with no stacked dependency or release tag. Use a maintainer squash merge
to satisfy master's existing linear-history and restricted-update rules. The PR
is left unmerged; no repository protection is changed.

Final local qualification on `68b638d9e`:

| Check | Result |
| --- | --- |
| `make test-all -j16 TEST_JOBS=8` | 721 passed, zero failures/timeouts/signals; 672.99 seconds. Includes development/production builds, sanitizers and the full flat-file flight journey. |
| `make test-db` | All 73 legs passed in 443 seconds. After the final carrier-identity refinement, the affected MariaDB flight journey was rerun against the final server and passed again; the other database code and tests were unchanged. |
| `tests/async/with_disposable_mariadb.sh python3 tests/async/test_flight_network_journey.py --backend mariadb --server bin/server/dms_new` | Final MariaDB flight journey passed all discovery, fare, unavailable-ticket, logout-return, copyover, epic, persistence and corpse checks. |
| `scripts/check_tests_catch.sh 6df413724 68b638d9e` | All three changed regressions pass on the repaired code and fail on the reviewed revision: native flight commands, full-world flight journey, and public crumbleloot removal. |
| `./scripts/format.sh --all --check` | All 1045 tracked C/C++ files passed. Commit hooks also passed formatting and clang-tidy. |
| `make security-check` | Dependency baseline and source/configuration checks passed. |
| `npm test --prefix site` | 15 tests passed against the updated documentation; locked dependencies were installed with `npm ci --prefix site`. |

Both backend journeys prove ticket retention during paralysis and a carrier's return
following immediate post-arrival logout, in addition to the original complete
feature journey. The final MariaDB binary SHA-256 is
`d70f9713a4e65e3529658eb2fd95578cdee2b5f1aa070218c0dc42e129b978b8`.
Full servers use development builds; the native command/removal/recovery tests use
ASan/UBSan. The final documentation commit changes no server or test behavior.

## Requirements and decision authority

The [builder's decisions](https://github.com/LuminariMUD/Duris/issues/40#issuecomment-6115125249)
supersede the issue's original spreadsheet snapshot and unanswered questions. The
[epic-zone exception](https://github.com/LuminariMUD/Duris/issues/40#issuecomment-6115189113)
and the issue's subsequent clarification govern dedicated epic-zone access.
For persistence, use the current
[memory-authority decision](../adr/0002-persistence-reset-memory-is-the-authority.md)
and [player save pipeline](../persistence/PLAYER_SAVE_PIPELINE.md), rather than the
issue's older persistence suggestions.

The required outcome is:

- The 25 ordinary stops use the corrected landing rooms and builder names below.
  The two epic-only services retain their original departure pads.
- Characters start with no learned stops. Their first `list` at an ordinary flight dragon
  discovers that dragon's ordinary stop; repeated visits do not award EXP again.
- From a participating ordinary dragon, characters can buy flights to their learned ordinary
  stops. Ordinary travel has no level or race restriction; the fare is the barrier.
- Normal fares use 0.5 platinum per room flown. Listings sort by distance.
- `flights` displays the character's learned stops anywhere, including during flight.
- Discovery EXP grows with discoveries and scales with the character's EXP-gain cap;
  rested bonuses apply. Use the approved formula in the resolved decisions below.
- Discoveries belong to the character, survive saves and restarts, and reset at pwipe.
- Extra Destinations remain specific trips from designated dragons. Epic entrances
  cannot be learned as normal network stops or reached with unrestricted tickets.
- Existing transport recovery, singleton reconciliation, passenger handling, and
  return movement continue to work.
- Named dragons remain killable and leave corpses for the builder's separate quests.

## Epic access explained

Scorched and Snow Ogres keep their existing departure dragons, fixed fares and
level gates. Players reach those dragons by other means, buy the dedicated one-way
trip, and leave the epic entrance by other means. Neither the departure stop nor
the epic entrance can be learned or reached through the ordinary network.

The dragon returning home after a drop-off does not create a passenger return
service. Fotenak's earlier proposal included the departure stop in the network; the
user's 2026-10-12 exclusion supersedes that proposal. Other services remain ordinary
stops even when near epic content. Storm Port may serve its ordinary network plus
its separate Stronghold extra trip.

## Resolved decisions (2026-10-12)

| Decision | Selected behavior and authority |
| --- | --- |
| Epic departure stops | User excludes services 47015 and 47027 from the ordinary network entirely. No learning, ordinary ticket purchase, or ordinary destination for either service; their dedicated trips remain. This supersedes Fotenak's proposed inclusion. |
| Normal fares | User delegated the bound choice: charge exactly 500 copper per path step, no minimum/maximum, no rounding. |
| Discovery EXP | User approved `current EXP-gain cap * new discovery count / 27` before normal rested, racial and global modifiers/caps. The later exclusion of two stations leaves 25 available discoveries; retain the approved divisor. |
| Scorched route | Service 47015, origin 576577, landing 579365 on Scorched Island, 200p, level 51+, one-way. Verified by the connected land path and continent seed below. |

These choices apply to the complete implementation and its PR. No production deployment
or database changes are authorized by this plan.

## Service catalog (25 ordinary stops and two epic-only departures)

Use the following permanent bit assignment for learned stops: bit `mob_vnum - 47015`.
Store the assignment explicitly in the catalog, independent of its display order.
Moving a landing pad or changing a display name must not change the learned identity.

| Bit | Service mob | Landing room | Ordinary destination | Carrier |
| --- | --- | --- | --- | --- |
| 0 | 47015 | 576577 | The Isle of Undeath | Corrosyvile, the ancient black dragon |
| 1 | 47016 | 635756 | Quietus Quay | a huge wyvern |
| 2 | 47017 | 588326 | Storm Port | a mailed wyvern |
| 3 | 47018 | 606262 | Bloodstone Keep | an armored wyvern |
| 4 | 47019 | 514072 | Myrabolus | a great white hippogriff |
| 5 | 47020 | 582084 | The City of Torrhan | a great white griffin |
| 6 | 47021 | 543701 | Ugta | a huge griffin |
| 7 | 47022 | 545407 | Venan'Trut | a flying carpet |
| 8 | 47023 | 563522 | Fort Boyard | Azerathrax, the ancient blue dragon |
| 9 | 47024 | 622276 | Sarmiz'Duul | a large wyvern |
| 10 | 47025 | 519043 | Fort Khoralator | a harnessed roc |
| 11 | 47026 | 543662 | Kimordril | a harnessed griffin |
| 12 | 47027 | 619771 | Swamp of Chief Blood-Eye | Krrlytstalarryn, the ancient red dragon |
| 13 | 47028 | 522247 | Helgor Outpost | a harnessed frost drake |
| 14 | 47029 | 631413 | Clan Shatter Stone | a harnessed wyvern |
| 15 | 47030 | 514279 | Bone Fort Inn | Cryoss, the ancient white dragon |
| 16 | 47031 | 533479 | Winterhaven | a mighty roc |
| 17 | 47032 | 584293 | Shady Grove | a mighty wyvern |
| 18 | 47033 | 570024 | Tharnadia | a mighty griffin |
| 19 | 47034 | 529229 | Fenaline | a large hippogriff |
| 20 | 47035 | 546144 | Canderthal Harbor | a large griffin |
| 21 | 47036 | 575328 | Nizari | Aurumax, the ancient copper dragon |
| 22 | 47037 | 641295 | The Jade Empire | Verdax, the ancient jade dragon |
| 23 | 47038 | 634060 | Dalvik's Dockyard | a mighty great eagle |
| 24 | 47039 | 577835 | Varathorn Keep | a huge skeletal dragon |
| 25 | 47040 | 616547 | Thur'Gurax | a large wyvern |
| 26 | 47041 | 557220 | Moonshae Island | Glimmyris, the ancient faerie dragon |

**Services 47015 and 47027 are epic-only under the user's final decision.** Their
rows retain the permanent bit assignments for reference, but bits 0 and 12 are
reserved and never taught or listed by the ordinary network. All 27 service mobs
still initialize. Do not exclude other surface stops merely for proximity to epic content.

The full-world journeys load all 27 services and corrected landing rooms, and all
603 routes are available. Every landing pad is a ground sector; both backend
journeys complete the ordinary and epic flights. The native fixture also exercises
the new Storm Port Stronghold trip at level one.

Fort Boyard uses `563522`, not the historical spreadsheet's `564319`. Torrhan uses
`582084`, not the old service origin `580080`. Recompute paths; do not reuse the old
distance matrix. Preserve ANSI destination names from the builder data, apply the
corrected dockyard name, and terminate formatting. The empty `47042` placeholder and
the dropped Behemoth Herders proposal are outside this catalog.

## Extra Destinations

| Service mob | Origin | Destination | Trip | Fare and restriction |
| --- | --- | --- | --- | --- |
| 47027 | 619771 | 620606 | Snow Ogres cavern approach | Existing 50p, level 51+, one-way. Preserve. |
| 47015 | 576577 | 579365 | A Desolate Island | Existing 200p, level 51+, one-way to Scorched Island. Preserve. |
| 47017 | 588326 | 637082 | Storm Port Stronghold | Proposed new extra trip: 10p, level 1 in the retained sheet, one-way. |

The sheet's older proposed 100p fares do not override the issue's requirement to
preserve exempt routes. Extra Destination costs are treated as platinum, consistent
with the current service. Keep any existing trusted-staff exceptions; do not extend
them to ordinary players or add a general bypass.

Snow Ogres is source-confirmed: the flight lands at `620606`, west leads to `620605`,
and down leads to zone room `87700`. Scorched's zone entrance is `71201`, connected to
surface room `576166`. The existing Desolate Island service (mob `47015`, origin
`576577`, landing `579365`) is now confirmed as its dedicated access route: the
landing reaches that continent seed over nine reciprocal, same-zone, non-ocean
exits: `579365 → 578965 → 578565 → 578165 → 577765 → 577365 → 576965 → 576565 →
576566 → 576166`. `src/world/map.c` names that seed `CONT_SCORCHED`;
`areas/wld/scorchvalley.wld` links it to `71201`. This establishes the island
classification without equating a display name with a zone. The original route
inventory contains two dedicated epic routes; both retain their existing gates.

## Implementation sequence

### 1 (complete) Finalize the catalog and route classification

Replace the normal-stop metadata in `src/world/transport.c` with the catalog above
and a separate Extra Destination table. Keep route eligibility tied to the service
and destination, rather than inferring it from a display name or proximity to a zone.

Validate unique service mobs, landing rooms, and discovery bits; verify all referenced
records are loaded by the actual world. Enforce the confirmed Scorched mapping and the
departure-stop exclusion recorded above. Retain the seven named dragons' combat and corpse behavior.
Their `Quest? = Y` flag does not turn learning a stop into a quest reward.

Proof: the corrected catalog loads, existing ordinary routes are replaced coherently,
the eleven new service mobs are initialized, and each exempt destination has exactly
its designated access route. Behemoth Herders and the placeholder do not become stops.

### 2 (complete) Add learned stops to character status

Add a zero-initialized `uint64_t` learned-stop mask to the player data structure and
an unsigned status field to the existing player snapshot. Save it in one
`player_data` column, `learned_flight_stops BIGINT UNSIGNED NOT NULL
DEFAULT 0`. Reuse `PLAYER_COMPONENT_STATUS`, which already contains EXP.

Update capture, SQL column mapping, SQL loading, materialization validation, and the
snapshot codec. The planning baseline had 63 integer status fields and schema 7;
the implementation now uses 64 fields and schema 8 for the added discovery mask.
Preserve decoding of currently supported old formats, including versions 1, 3, 5,
and 7, defaulting their missing flight field to zero. Keep stored field IDs stable.
Version any incompatible encoding change explicitly and test old-file loading.

The flat-file backend already replaces status as a unit. Verify that the mask follows
that path, including partial saves of unrelated components. No flight-specific
repository or additional dirty-component bit is needed.

Add a guarded, re-runnable immutable migration and its verifier. The implementation uses
`0038_learned_flight_stops`, after `0037_session_audit_identity`. Update migration checksums, runtime schema contracts, and
the applicable bootstrap path. Do not change historical migrations or invent another
table solely for discoveries.

Explicitly reset the mask in the SQL pwipe operation and its preflight/postflight
checks: `player_data` is deactivated rather than deleted. Verify that fresh or
reactivated characters cannot inherit a previous season's discoveries. Verify existing
character deletion, export, and flat-file character lifecycle behavior; add only the
changes those paths require. Do not add a new flat-file wipe subsystem.

Proof: new characters start empty; SQL and flat-file saves retain the mask; old saves
load; catalog reordering does not change learned identities; account siblings have
independent masks; wipe and recreation reset progress.

### 3 (complete) Build paths and fares through the existing service

Build route metadata before `transport_restore()` needs to resolve saved endpoints.
Keep `initialize_transport()` after world recovery, preserving singleton reconciliation.
Do not move mob spawning ahead of recovery to make the new catalog convenient.

Precompute paths at startup with a small transport-local breadth-first traversal from
each ordinary origin. Every flight edge has unit cost. Reuse the existing reciprocal
exit, same-zone, blocked-exit, and map-wrap rules; respect the pathfinder's visited-mark
lifecycle. Include each origin's Extra Destinations in its traversal. Retain only the
paths needed by the catalog. This replaces hundreds of independent pair searches
without introducing a general graph framework or command-time pathfinding.

Normal distance is the actual path length. Charge 500 copper per room before any
subsequently agreed bounds or rounding. Use the existing wallet and coin formatting.
Apply no distance formula or ordinary restriction removal to exempt routes. Log and
omit unavailable routes; never substitute an unrestricted route to an epic entrance.

Preserve current movement callbacks, timing, dismounting, and empty-carrier return.
Continue saving origin, destination, state, step, and rider through the existing
`transport_snapshot`; do not change copyover or Redis transport formats unnecessarily.
Validate restored positions against the recomputed path. Valid occupied flights resume
once, empty carriers return, and incompatible or invalid recovered routes land safely
at the configured home. Retain item transfer and safe passenger landing when removing
duplicate service mobs. Bound-check runtime route and path-step access.

Proof: paths reach their declared endpoints, corrected routes use their new pads,
fares match distance, invalid routes cannot start, and repeated initialization and
recovery preserve one dragon/sign/event as applicable. Measure startup cost on the
full world; do not move route searches into the game loop to hide startup work.

### 4 (complete) Implement discovery and travel commands

On the first valid player `list` at a waiting service dragon, learn only that dragon's
ordinary stop. Add no discovery flags for its Extra Destinations. Repeated calls must
be idempotent. Keep service commands unavailable while the carrier is busy.

Use one local selection function for `list` and `buy`, because they must agree on
eligibility, ordering, numbering, and fares. List learned ordinary destinations other
than the current stop, sorted by path distance with permanent ID as the tie-breaker.
Show eligible Extra Destinations distinctly as one-way trips. Hide unlearned ordinary
stops rather than revealing the whole exploration catalog. Preserve existing trusted
staff access behavior without adding automatic all-destination discovery.

Add `CMD_FLIGHTS` to the command registry without renumbering existing command IDs.
Update `MAX_CMD` and register a read-only handler in the normal interpreter. Explicitly
allow it through the transport proc's in-flight command restriction. It lists known
stops without learning anything, granting EXP, or offering tickets remotely.

For the anywhere display, the implemented order is distance from the
current surface room or a mapped zone entrance. Reuse existing map-location lookup
where suitable. Display order away from a station may use cheap map distance, clearly
distinguished from a ticket quote based on the actual flight path. If no map position
is available, show known names in stable order with distance unavailable. Do not run
a full-world search each time someone types `flights`.

Retain ticket object `47008`. Store departure service and destination room in its
existing values instead of a route-table index. Resolve the permitted route through
the catalog when redeeming it. Validate the actual recipient, origin location, service
state, learned destination, applicable level/access gates, and nonempty path before
consuming the ticket or mounting the player. Recheck access on redemption so handing
a ticket to another character cannot bypass discovery or epic restrictions.

Copy needed ticket fields before `extract_obj()`, which frees the object. Reject
malformed, obsolete, or wrong-origin tickets safely without consuming them. Old
route-index values must never become valid destinations accidentally. Preserve the
existing combat, riding, and flag-carrying restrictions. Keep ticket charging and
creation on the existing money/item paths, with no charge when creation fails.

Proof: exercise production `list`, `flights`, `buy`, and `give` handlers, including
empty lists, ties, unknown destinations, insufficient funds, busy carriers, transferred
tickets, malformed values, and epic-route bypass attempts.

### 5 (complete) Award discovery EXP with the discovery state

Using the approved count/27 formula, compute the base reward from the character's current
EXP-gain cap and new discovery count. The old flat 10k examples are superseded.
Use the existing EXP award path for rested bonuses, the global difficulty modifier,
caps, level advancement, logging, and telemetry. Reuse `EXP_QUEST` if ordinary racial
modifiers are retained. If Fotenak explicitly requests different racial treatment,
make only the narrow EXP-path change that policy requires.

Set the learned bit and grant the reward in the same game-thread command, then let
the existing status checkpoint save both. Trace any save triggered during EXP/level
advancement so it cannot persist only one half. Neither the database nor a separate
reward acknowledgement should block learning in memory. Do not add a reward journal,
receipt table, or independent writer.

The persistence guarantee is that a saved reward cannot survive without its discovery
flag. An unsaved discovery and reward may both disappear in a crash, following the
existing checkpoint model. Redis world recovery is not required for learned stops.
Repeat visits after loading a saved discovery must not grant the reward again.

Show a discovery notice. Ensure any reward amount shown reflects what was credited,
including capped characters and level-ups; do not assume the difference between EXP
before and after a level-up is the awarded amount. A character that cannot receive
EXP still learns the stop once. Do not promise a deferred reward on a later visit.

Proof: growth and cap-relative scaling match the agreed formula; rested and racial
policies are correct; capped and immortal characters do not get a repeatable award;
relogs, queued saves, save failures, and crashes cannot preserve a reward while
forgetting its discovery.

### 6 (complete) Complete guidance and integrated verification

Update sign `420` in `areas/obj/heavens.obj` to explain discovery and `flights`.
Add flight help through the maintained help sources and import path, covering both
SQL and flat-file help. Explain `list`, `flights`, `buy`, and ticket redemption, fares,
per-character discoveries, and the separation between ordinary stations and special
one-way trips. Update the transport recovery documentation and record completed
regression evidence when implementation is verified.

Extend existing tests before creating new harnesses. The singleton test slices
production `transport.c` at `// Handles list command` and
`int do_simple_move_skipping_procs`; preserve those markers or update the harness
deliberately. Its existing slice excludes command handlers, so it cannot alone prove
discovery, purchase, or redemption behavior.

Add focused executable coverage for the new commands and a real gameplay journey
using the established journey utilities. Run it against SQL and flat-file persistence
where applicable, with local test characters and disposable data. Include ordinary
travel, the separate epic access trip, relogging, and restart/copyover. Preserve checks
for recovery with an occupied dragon, an empty returning dragon, and duplicate dragons.

Deliver the feature as one coherent change. Intermediate commits may follow these
steps, but do not release a version with every destination unlocked or discovery EXP
missing. Production migration and deployment remain separate authorized actions.

## Files and responsibilities

| Existing files or area | Necessary work |
| --- | --- |
| [transport.c](../../src/world/transport.c), [transport.h](../../src/world/transport.h) | Catalog, special routes, path preparation, discovery, fares, command selection, ticket validation, and recovery integration. |
| [structs.h](../../src/core/structs.h) | Per-character learned-stop mask. |
| [player_snapshot.h](../../src/player/player_snapshot.h), [capture](../../src/player/player_snapshot_capture.c), [codec](../../src/player/player_snapshot_codec.c) | Status field, bounded capture, wire compatibility, and defaults for old saves. |
| [snapshot repository](../../src/player/player_snapshot_repository.c), [load repository](../../src/player/player_load_repository.c), [materialization](../../src/player/player_load_materialize.c), [flat-file repository](../../src/flatfile/flatfile_player_repository.c) | Store and restore the new status field through both existing backends; change flat-file merging only if needed. |
| [interp.c](../../src/cmd/interp.c), [interp.h](../../src/cmd/interp.h), [config.h](../../src/core/config.h) | Append and register `flights`; update command counts. Keep its declaration with the transport interface. |
| [limits.c](../../src/world/limits.c) | Reuse existing EXP handling; edit only if the agreed policy or accurate reward reporting requires it. |
| [migrations](../../migrations), [runtime schema contract](../../src/core/runtime_compatibility_contract.h), [sql.c](../../src/sql/sql.c) | Additive column, verifier and manifests, required boot checks, pwipe reset and verification. |
| [vehicles.mob](../../areas/mob/vehicles.mob), [heavens.obj](../../areas/obj/heavens.obj), maintained help sources | Preserve builder records and named-dragon behavior; change only required content, including the sign/help. Do not hand-edit generated combined areas. |
| [tests/async](../../tests/async), [database test runner](../../tests/run_db_tests.sh) | Extend command, snapshot, persistence, migration, lifecycle, and recovery coverage; register any new database journey. |
| [WORLD_SINGLETON_RECOVERY.md](../operations/WORLD_SINGLETON_RECOVERY.md), [REGRESSIONS.md](../testing/REGRESSIONS.md) | Explain the completed behavior and record actual validation evidence. |

No new persistence component was needed in `player_revision_state.h`: discoveries and
EXP share status. File copyover version 16 and Redis generation schema 13 are
unchanged; the existing endpoint-based transport snapshot already expresses the journey.

## Proof and completion criteria

| Requirement | Required evidence |
| --- | --- |
| Corrected catalog | All 25 ordinary pads and two epic-only services load; IDs remain stable under catalog reordering; corrected Fort Boyard/Torrhan routes are used. |
| New and existing dragons | All configured services initialize once; named dragons remain killable and leave corpses; repeated initialization creates no extras. |
| Discovery and commands | First `list` teaches one ordinary stop; repeats do nothing; `flights` works away from dragons and while flying; unknown normal stops cannot be purchased. |
| Ordering and pricing | Distance ordering and tie-breaks are stable, `list`/`buy` agree, normal fares match the approved formula, and extras retain their own fares. |
| Ordinary access | Low-level and different-race characters can use learned ordinary routes without the removed travel gates. |
| Epic exceptions | Each exempt route retains its origin and access rules; neither its departure nor entrance can be learned as an ordinary stop; no return station appears there. |
| Ticket integrity | Transferred, forged, stale, wrong-origin, unknown-destination, and out-of-range tickets cannot bypass access or corrupt movement; valid tickets still work. |
| EXP | Agreed discovery scaling, rested behavior, race policy, caps, and level-up behavior hold; repeated discovery cannot duplicate a durable reward. |
| Persistence | SQL and flat-file round trips, old snapshots, unrelated partial saves, account siblings, relogs, save failures, and crash boundaries preserve the intended state. |
| Lifecycle | Pwipes and new/recreated characters start empty; deletion/export retain their existing character-data semantics. |
| World recovery | Occupied flights resume once; empty dragons return; invalid paths land safely; duplicate riders/items are preserved; old supported snapshots still load. |
| Schema | Fresh bootstrap, upgrade, repeat application, drift checks, and runtime boot compatibility pass on supported database variants. |
| Player journey | A real character discovers and flies between normal stops, sees a correct fare, uses a restricted special trip only from its origin, and retains progress after relog/restart. |
| Documentation | Sign and help explain the actual behavior; links resolve; recorded regression results identify the implementation tested. |

During implementation, run the smallest relevant checks after each change. Existing
starting points include:

```bash
python3 tests/async/test_world_singletons.py
python3 tests/async/test_player_snapshot_capture.py
python3 tests/async/test_player_item_snapshot_codec.py
python3 tests/async/test_flatfile_player_repository.py
python3 tests/async/test_player_save_pipeline.py
python3 tests/async/test_player_load_pipeline.py
python3 tests/async/test_data_lifecycle_manifest.py
python3 tests/async/test_personal_data_export.py
python3 tests/async/test_account_erasure.py
python3 tests/async/test_documentation_contract.py
tests/async/run_player_load_repository_mysql.sh
```

Existing persistence fixtures were extended with discovery assertions. The additional
`tests/async/test_flight_network.py` executes production handlers under ASan/UBSan;
`tests/async/test_flight_network_journey.py` drives real full-world clients and is
registered in both applicable gates. Both pass; the journey's SQL leg uses
`--backend mariadb --server bin/server/dms_new` under the disposable database wrapper.

Final implementation gates:

```bash
./scripts/format.sh --check
make -C src
make test-all
make test-db
```

The full gates are appropriate because the feature touches shared player structures,
snapshot compatibility, migrations, and transport recovery. Include the new journey
in the appropriate runner; check the existing migration engine/runtime legs on the
supported MySQL/MariaDB variants. Use the disposable database wrappers described in
[TESTING.md](../guides/TESTING.md). Reuse valid results rather than repeating green
checks without a relevant change. Verify the running executable when testing a built
server; the supervisor can consume or replace `dms_new`.

All final feature gates passed. The review handoff records the tested revision,
commands, results and runtime evidence.

## Ablation and non goals

| Decision | Reason |
| --- | --- |
| Keep the existing transport service and movement callbacks | They already implement flight, passengers, home return, and recovery. |
| Keep a separate Extra Destination table | Epic access and ordinary learned travel have different required rules. |
| Use one saved status mask | The 25 discoveries and two reserved identities fit in one scalar and must be saved with EXP. |
| Share route selection between listing and buying | Both real callers must use identical eligibility and numbering. |
| Precompute paths from each origin | The larger network needs many destinations per origin without command-time searches. |
| Drop a discovery table, repository, and dirty component | Existing character status already supplies storage and atomicity. |
| Drop a reward journal, receipt table, and second writer | The current persistence model saves discovery and EXP together. |
| Drop a general route framework, live editor, and configuration surface | This feature has a fixed builder catalog and existing transport ownership. |
| Leave dragon quests, ferry changes, and unrelated world cleanup outside this feature | They are separate work; preserve compatibility with the builder's dragon quests. |
| Drop an unrestricted intermediate release | It would bypass the required discovery and epic-access behavior. |

Implementation is complete only when every
required behavior has its corresponding proof, and the final diff contains only the
necessary feature, compatibility, test, and documentation changes. Keep progress and
decision updates in this file while the project remains open.
