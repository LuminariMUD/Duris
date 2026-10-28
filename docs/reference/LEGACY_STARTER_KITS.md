# Standard starter-kit preparation

The standard kit table is initialized once and selects an ordered, owned plan from
copied race, class, alignment, override, and special-item inputs. Repeated VNUMs
are intentional. The game-thread capture adapter snapshots spell IDs and weapon
admission using the existing skill and item-use predicates; pure preparation
filters unavailable or inadmissible items before any live object is allocated.

During boot, after the object index, pool and special-procedure setup, `boot_db`
parses every VNUM enumerated by the same kit table and its special additions.
`object_template` owns strings, extra descriptions and scalar prototype fields.
Cache construction creates no object identity, live object, list entry or event.
Missing VNUMs are logged at boot and omitted. Runtime cache misses cannot fall
back to file parsing.

`instantiate_object_template` runs on the game thread. It registers the live
object, preserves nullable/shared indexed text and independent extra descriptions,
and invokes runtime procedures, events and object conversion. Ordinary
`read_object` callers use the same parser/publication implementation and retain
cold loading and the shared-index-string fast path. Starter publication applies
cost/transience, spellbook counts and keywords, then uses `obj_to_char`
and the existing creation-grant coordinator.

The durable character baseline still precedes kit submission. A busy coordinator
prevents a repeated request while earlier items are awaiting publication, even
when carried inventory is empty. Grant validation and publication resolve retained
live characters by PID, so losing a descriptor does not abandon a committed item
or the remaining queue. Existing ownership revisions, operation IDs, retries,
replay receipts, command/prompt gates, and snapshot save ordering remain authority.
No new worker, persistence format, database migration or recovery queue is added.

## Transient gear and ownership

`ITEM_TRANSIENT` controls dissolution after dropping. `ITEM_NORENT` remains a
request not to retain an unowned runtime item, but it cannot silently override an
active durable-custody row: authoritative items are serialized until an explicit
destruction transition retires that custody. Eligible transient gear, including
flags inherited from prototypes, must acquire active player custody through
`obj_to_char()` before publication. Containers and quivers are exempt from the
standard kit's added transient flag, as are missiles. Those exemptions do not
erase prototype flags or replace ownership admission.

New regular legacy starter arrows therefore follow normal ammunition behavior:
a missed shot in a dry room leaves the arrow available for its owner to
gather, including after moving to an adjacent landing room. Successful-hit
wear/scrapping and returning arrows keep their existing behavior. The starter
bow still receives the added transient flag, and the small quiver retains its
prototype flag; deliberately dropping either still dissolves it.

The missile exemption applies when a new item is materialized. Previously
granted arrows retain their saved flags, and destroyed arrows are not recovered.
There is no save migration or load-time rewrite. An explicitly transient missile
prototype also retains its authored behavior.

Gathering respects the quiver's existing capacity and ammunition family before
moving an owned missile from the floor or a corpse. Excess or incompatible
missiles stay at their source. Each shot makes an independent shield-block
decision. Broken missiles remain valid through damage messages and enchantments,
then are scrapped; if the victim has died, the detached broken missile is extracted.
Mark creation and expiry use owning string setters; expiry reads the shared index
text without creating another live arrow.

Snapshots retain eligible transient UIDs, flags, equipment slots, and container
relationships. The loaders apply the ownership filtering described in
[PLAYER_SAVE_PIPELINE.md](../persistence/PLAYER_SAVE_PIPELINE.md#what-a-load-reads).
An item marked transient follows the same ownership rules as other items; that
flag is not an alternate recovery or admission path.

`extract_obj()` is a general teardown primitive and does not itself retire
custody. Gameplay destruction requiring a durable record must use
`item_transfer_reason::destruction`; adding unconditional transactions to every
shutdown/copyover extraction would violate that lifecycle boundary.

## Verification

Focused tests are automatically discovered by the normal regression runner:

- `test_newbie_kit_plan.py`: kit-table digest, selection combinations,
  template enumeration, pure preparation and
  integration boundaries. Includes the inclusive `LAST_RACE` boundary safely.
- `test_newbie_object_template.py`: actual parser/cache/publication functions,
  closed-file instantiation, allocator ownership, nullable strings, B5/A/T data,
  normalization and deferred runtime hooks, with ASan/UBSan.
- `test_newbie_grant_lifecycle.py`: held completion, unrelated actor dispatch,
  linkdead and replacement-character publication, duplicate completion,
  rejection cleanup, refused admission/retry and pre-entry grants, with ASan/UBSan.
- `test_fired_missile_encumbrance.py`: production materialization, fire/gather,
  room placement and decay callback, with controlled allocation, RNG and event
  dispatch under ASan/UBSan. Covers both Ranger kit selections, starter/ordinary
  missiles, same/adjacent-room misses, PID ownership, weight/count restoration,
  authored transience, bow/quiver decay, successful-hit wear and returning shots.
  Exercises real string setters/freeing and heap retirement, melee/enchantment
  death cleanup, repeated mark expiry, room/corpse capacity and family checks,
  and blocked-then-unblocked volleys in both room arrangements.
- `test_starter_arrow_journey.py`: fresh legacy Ranger grants and actual
  fire/event/gather commands through Telnet on a disposable minimal flat-file
  server, with saved UID, condition, quiver count and weight checks. The fixture
  explicitly enables historical races/classes; it is not a live roster claim.
  Commands wait for their own response before accepting a prompt. A socket-pair
  control checks buffered and arriving notification prompts; notifications remain
  in the complete transcript rather than becoming command results.

Run those focused checks against the current tree. They use synthetic fixtures;
they are not a live latency benchmark or production database test. Replay
guarantees remain per accepted ownership operation; there is no durable kit-level
receipt.
