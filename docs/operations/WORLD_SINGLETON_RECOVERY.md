# Shop and flight singleton recovery

Issue #235 reported five copies of flight dragon 47030 and sign 420 at room
543662, and six copies of keeper 29429 at shop room 29437. Startup created
transports and restored saved keepers before world recovery loaded more copies.

Transport initialization now runs after file copyover, Redis clean/crash
recovery, or the Redis normal-boot fallback. It reuses the service's dragon
anywhere in the world and keeps one sign at each configured origin. Repeated
calls do not create extra dragons, signs, or movement events. Only the explicit
transport catalog and signs at its origins are reconciled.

The flight catalog has 27 services: 25 discoverable ordinary stops and two
separate epic-only services. Catalog discovery bits remain fixed when a pad or
name changes. Endpoint metadata is available before recovery reads transport
snapshots; paths are computed once from each origin after the world loads.
Ordinary tickets hold the service mob and destination room, so table reordering
cannot redirect them. Redemption rechecks the recipient's learned stop or the
extra trip's level gate before consuming the ticket.

Character discoveries live in player status with EXP, independently of transport
or Redis recovery. Snapshot schema 8 reads supported old player files with an
empty discovery mask. Migration `0038_learned_flight_stops` adds the SQL column;
pwipe clears it on retained player rows. The two epic departure stops and their
entrances cannot be learned or used as ordinary network destinations.

New snapshots retain a transport's origin, destination, movement state, path
step, and passenger name. Recovery validates the saved position against the
recomputed route. A co-located recovered passenger resumes the flight. An
unoccupied dragon returns along its route. Missing, obsolete, or invalid route
state returns the dragon to its configured origin. When old duplicates include
multiple occupied dragons, one flight survives and extra passengers are landed
at that service's origin before their extra dragon is removed. Carried and worn
items on retired dragons are transferred to the survivor.

Current file copyover version 17 accepts versions 12 through 17. Version 17
preserves complete NPC item trees and their stable root UIDs, including worn and
nested artifacts; native restore attaches those qualified roots to the restored
NPC even when transport rules relocate it. Version 13
introduced the transport endpoints and rider state; version 12 flights lack that
state and return home. Current Redis world generations use schema 13, while the
NPC codec accepts the original record and its bounded optional `TRN1` transport
tail. The flight network changes neither format. Generation schema checks remain
strict; see [World recovery format](../persistence/WORLD_RECOVERY_FORMAT.md).

Shop inventory has different authorities in each recovery mode:

- Native copyover reuses UID-matching stock already restored from the authoritative
  catalog. Singleton reconciliation keeps that catalog keeper, preserving complete
  item properties and trade revisions without replaying its stock a second time.
- SQL copyovers commit each live keeper's complete shop snapshot after
  persistence drains and before publishing the copyover file. Any save failure
  cancels the copyover while the server remains live. Startup retains these
  durable keepers, preserving custom item state omitted by basic NPC records.
  Legacy version 12 files use their live keeper inventory instead of older SQL
  snapshots because they did not make this checked shop save.
- Redis restores NPC location/state without inventory. Its reconciliation
  retains the keeper already restored from the durable shop store and removes
  recovered duplicates and their regenerated template stock.
- Flat-file trade records remain authoritative for item custody and shop revisions.
  Native recovery reuses their restored live bodies when their shop and UID agree.
- Without a durable incumbent, reconciliation selects the recovered keeper
  with the most stock/equipment, breaking ties by instance ID. File-recovered
  duplicates contribute their non-produced stock and equipment to the survivor.
  Produced stock is replenished for the selected shop.

Shop binding uses the configured room, birthplace, or an unambiguous roaming
shop. Two shops may share a mobile vnum. Flat-file restoration replaces matching
mobile/room incumbents, and shop commands use the same room-aware binding.
Unbound ordinary NPCs and objects are outside this cleanup.

`python3 tests/async/test_world_singletons.py` compiles production reconciliation,
movement, and NPC capture/restore code with isolated world I/O under ASan/UBSan.
It covers the reported records, duplicate snapshots, five stock recovery cycles,
five passenger recovery cycles through the wire codec, completion and return of
the flight, repeated initialization, durable stock/equipment, shared vnums, and
legacy/occupied duplicates. Existing shopkeeper population tests exercise normal
and forced resets. Existing recovery pipeline tests exercise failed Redis
materialization and fallback. These are isolated regressions, not a production
recovery experiment.

A full-world boot or copyover applies reconciliation and logs the number of extra
keepers and dragons removed.

Runtime flight continuation belongs to the carrier alone, including on occupied
trips. Passenger extraction therefore removes the riding link without cancelling
the carrier's next movement. Each callback checks the carrier's actual route
position and current rider; an interrupted trip returns empty, while invalid
progress lands the carrier at its configured pad. Separately relocated players
are detached without being pulled back home. Arrival detaches and grounds the
delivered passenger unconditionally, even where the ordinary dismount command
would refuse. The carrier returns at flight altitude and lands at its own pad.

A flight accepts one player who has neither a mount nor a rider. Ticket refusal
preserves the ticket and wallet. Ordinary mounting cannot attach a rider to a
service carrier or its active passenger. Legacy nested passengers found during
recovery are all detached and grounded before landing at home. Entering combat
without mounted-combat skill does not dismount a paid passenger; ordinary ground
mounts and existing attack/altitude rules keep their normal behavior.

`python3 tests/async/test_flight_transport_runtime.py` uses production transport,
riding-link functions, event scheduling and cancellation with isolated room I/O.
It covers passenger link teardown/freeing between and during movement, owner
extraction during occupied and empty movement, generic victim cancellation, and
return to service. It complements the full-server flight journey; its simulated
room entry and character allocation do not prove a production attack sequence.

Flight relocation checks character identity and liveness after both departure and
entry callbacks, including recursively moved riding companions. A refused or
redirected home placement keeps a single return callback pending; the carrier
becomes WAITING and clears its progress only after confirmed placement at home.
Duplicate retirement revalidates both carriers after landing before transferring
items or extracting the extra body. No new event type or recovery snapshot field
is needed.

`test_flight_network_journey.py` qualifies real commands and persistence on
disposable full worlds. `--interruptions-only` uses two learned stops for NPC
attack, outbound interruption, carrier reuse and reconnect checks;
`--reconnect-only` selects just the socket case. A ground NPC's melee attempt is
rejected against an elevated passenger; legal same-altitude combat retains the
paid ride. These checks do not identify the original reported attacker.
