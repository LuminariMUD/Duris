# World Recovery Pipeline

Optional Redis restart and crash recovery uses a long-lived in-process publisher instead of a
forked serializer. The game thread incrementally captures one sequence-numbered
generation across NPCs, floor objects, doors, and zone timers. Each call is bounded by
elapsed time, each record has a byte ceiling, and the complete retained generation has a
fixed memory ceiling.

The generation is an explicitly fuzzy recovery snapshot, not a point-in-time transaction.
Its timestamp is capture start, so age is conservative relative to every record. Capture
may span at most five minutes; an expired capture is discarded before publication, its
failure completion resumes the floor worker, and a later periodic request retries from a
new sequence. The game thread gives the capture at most 2 ms every second pulse (half a
second). Time is the only limit on a call: a step is one character, one object or one room
looked at, whether or not it is written, and the full world is 350,000 steps. Its capture
is about 40 calls, 20 seconds.

Fuzzy state is restricted to reconstructible NPC position/state, doors, zone timers, and
world-pop objects. NPC equipment and inventory are omitted, and NPC-carried gold is
captured as zero so a cross-time generation cannot replay currency into the persisted
player economy. Floor item trees retain stable UIDs and hierarchy. An object that changes
places while the capture runs can be met twice, in a container and by itself; it is
written once, in the tree it was met in first. Capture marks items
that have live SQL custody and omits trees whose custody disagrees with their floor
location; restore requires complete SQL reconciliation of every marked item before
materializing anything. An unmarked item is looked up at restore. When an ownership record
names an owner for it, other than a character whose save no longer has the item, it was
taken and saved after the capture: its tree is left out, since the holder has the item and
a second one would take the uid from them at the next taker's save. A record that names a
character whose save does not have the item is a dropped item's, and the item is restored.
Reconstructible world-pop objects stay HMAC-authenticated without
inventing SQL custody, and player corpses remain with the separate authoritative corpse
restore path. Player and ship state remain SQL-authoritative.

The publisher receives only owned framed bytes. It cannot traverse live characters,
objects, rooms, exits, or zones. It seals the generation with schema version, timestamp,
sequence, record counts, payload length, completeness, and CRC32.

## Atomic Publication

The worker passes the immutable generation blob to one Redis Lua compare-and-set. The
script verifies that this writer holds the lease, or that nobody does, and the expected
prior pointer while atomically writing
`mud:season:<epoch>:world_state:generation:<sequence>`, swapping the small
`mud:season:<epoch>:world_state:current` pointer and diagnostic metadata, consuming the
stable floor hash, and renewing the lease. A rejected script leaves the previous current
generation recoverable. After a verified swap, the previous blob is removed.

Boot trusts neither the diagnostic `valid` flag nor a partial key set. It loads the
current pointer and accepts the referenced generation only when magic, schema, header
size, exact sequence, age, payload length, completeness, record framing/counts, and
checksum all validate.

## Floor-Delta Boundary

Pending floor additions/removals are submitted to a bounded background worker. Before
capture, an ordered barrier confirms all earlier mutations and pauses publication of
later mutations. Only the exact acknowledged generation may atomically clear the stable
pre-capture hash. Completion or capture failure resumes post-barrier work. Each immutable
batch remains a hiredis pipeline, avoiding one network round trip per delta without
blocking the game loop.

A drop made while a capture runs is journaled after it, and the capture may have written
the item as well; so is a later drop of an item the generation holds in another place. Boot
refuses an item that comes twice, so it leaves out a floor record of an item the generation
holds: the item comes back where the capture saw it.

## Lifecycle And Health

The ordinary pulse advances capture and consumes typed completions. Copyover and
shutdown wait to bounded deadlines for capture, publication, exact acknowledgement, and
floor-boundary cleanup; failure cancels the process transition. `world persistence`
reports aggregate capture, queue, bytes, sequence, active/last capture age, expiry,
runtime, retry, and publication-failure health without object, room, or character identity.

An attempt that leaves no generation is counted: a capture that failed or expired, a
generation that did not publish, and an attempt that could not start because the writer
lease or the floor worker was unavailable. The third in a row raises one
`domain=world_recovery` persistence alert with the reason, the last published sequence and
its age; a published generation ends the run. The health outputs report that age as
`last_ack_age_s`.

The writer's lease is 60 seconds long and the game loop renews it every 20. A renewal, like
a publication, takes a lease nobody holds, so a writer whose lease ran out holds it again by
itself, and a crashed writer's is gone within a minute. A boot consumes the generation it
restored whoever holds the lease: a crashed writer's is usually still running, and a
generation left in place would be restored again at the next crash. A capture attempt that
could not start is made again 30 seconds later. A copyover releases the lease before its
exec, and the image it starts claims it at boot.

A graceful shutdown asks for one last capture after its drain, with the players saved and
gone, and waits for it to be published: a clean restart restores the world as the shutdown
left it. After a successful graceful drain, the fenced writer records an expiring marker for the
exact current sequence. Boot consumes that marker once and labels a matching valid
generation as clean-restart recovery. A missing or mismatched marker is crash recovery.
Successful materialization consumes only that exact generation and leaves the publisher
enabled for the new process lifetime.
