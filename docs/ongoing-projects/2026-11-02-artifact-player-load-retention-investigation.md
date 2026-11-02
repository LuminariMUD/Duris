# Artifact withheld on player load: stale ownership cache

Investigated on 2026-11-02 UTC. **A stale ownership cache can withhold a valid
artifact indefinitely across logins even after its saved payload and durable
custody agree. The failure is reproducible. Staff have no command to inspect the
conflicting cache entry or release the retained item through a fresh load.**

This explains a concrete failure mechanism for the reported
`artifact_identity/player_load` alert. Production evidence strongly supports this
mechanism for the reported gloves; the exact historical cache entry was not
logged and has not been observed directly. Do not turn that evidence limit into
an assumption that the saved item needs editing.

The investigation used production SELECTs and metadata reads, existing logs,
source and deployed executable inspection, and an isolated ASan/UBSan harness.
No production data, configuration, running process, or operational state was
changed. The only repository change from this investigation is this report.
The unrelated edits to `lib/etc/help` and `lib/reports/bugs` were preserved.

## Incident and evidence

At **11:10:43 UTC**, a player login emitted:

```text
PERSISTENCE: domain=artifact_identity/player_load action=custody_or_topology_mismatch outcome=alert detail=pid=<pid> first_vnum=67259 source_row=<row> action=retain_source_root
```

Vnum **67259** is **some fingerless gloves of su-monster skin**. The matching
`logs/log/artifact` entry supplies the physical UID and `error=116` (`ESTALE`).
The next entry in `logs/log/file` confirms `outcome=source_retained`, **one row,
136 bytes**, followed by successful entry into the game. Exact player IDs,
physical UIDs, source IDs, and other holders' names remain in the existing
restricted logs and database. This report calls the affected player the
recipient and the earlier holders A and B.

Read-only inspection at approximately 11:17–11:26 UTC found:

| Evidence | Result |
| --- | --- |
| Saved player payload | One glove, quantity 1, artifact flag present, saved as equipment, no container |
| Durable custody | Same UID and vnum; active; recipient-owned; context 0; root is its own UID; no parent; item revision 6 |
| Custody timestamp | Last updated **02:57:53.946137**, hours before the alert |
| Owner revision | Authority row exists; revision 523 at the initial read |
| Canonical artifact identity | Same UID; `present`; no rejected UIDs |
| Artifact tracking and binding | Owned, on the recipient, bound to the recipient; expiry and binding timestamps present |
| Retained payload creation | **04:39:40**, before the alert; same source row still exists afterward |
| Other inspected physical tables | No second row for this vnum or UID |
| Ownership children | None; this item is its entire retained component |
| Open ownership quarantine records for this UID | None |
| Transfer ledger and opening baseline for this UID | No rows; ordinary save claims do not require them |

The physical-table search covered `player_items`, `player_pet_items`,
`corpse_items`, `locker_items`, `account_locker_items`, `saved_items`,
`shopkeeper_items`, `siege_items`, and `auction_item_custody`. The canonical and
rejected identity search found only the matching artifact. This establishes the
inspected SQL state, not a complete audit of live bodies, Redis recovery,
embedded blobs, retained deliveries, or every other artifact source.

The ownership audit and logs establish the following timeline:

| Time, UTC | Evidence |
| --- | --- |
| Nov 1, 22:30:34 | Holder A entered the game during the same process uptime |
| Nov 2, 02:44:25 | Holder A died; the ownership audit records player A → A's corpse |
| 02:44:53 | The ownership audit records that corpse → player B |
| 02:57:53 | The ownership audit records player B → recipient |
| 03:00:41 | The artifact log records the gloves binding to the recipient |
| 04:39:40 | The saved equipment row was written |
| 11:10:43 | Recipient login retained the gloves and admitted the rest of the character |

The audit records claims made by saves; it does not prove the precise gameplay
command used for each handoff. The sequence is consistent with death, loot, and
a later player handoff. A prior holder's cache entry is a strong candidate for
the conflict. Its exact owner, root, parent, and revision cannot be recovered
from these log records.

An archived artifact log also contains this same alert category for another
artifact, vnum 67268, on October 29 at 04:33:13 UTC. That is a second historical
occurrence of the category, not proof that its cause or current disposition is
identical. The current uptime's artifact log contains one occurrence at the
time inspected.

## Confirmed failure path

There are three separate views of item ownership here:

1. The saved physical graph, such as `player_items` and its container links.
2. Durable custody, `item_current_owner`, captured with the load result.
3. The process-local map in
   [item_ownership_runtime.c](../../src/item/item_ownership_runtime.c).

The third view is a cache. The load predicate gives a stale entry in that cache
the power to reject the first two views even when they agree.

### A save advances durable custody without publishing it to the cache

Ordinary gameplay moves items in memory. For example,
[`do_give()`](../../src/cmd/actobj.c) unlinks the object, gives it to the new
owner, and marks both players' item components dirty. It does not publish an
ownership-cache transfer for an ordinary player-to-player give.

The writer calls
[`claim_items()`](../../src/item/item_claim_repository.c) through
`claim_graph()` in
[player_snapshot_repository.c](../../src/player/player_snapshot_repository.c).
When the durable owner or topology differs from what the saving player holds,
the claim updates `item_current_owner`, advances the item revision, and records
an ownership audit when the owner changes.

That writer operation does not update the game-thread ownership map.
[`finish_completion()`](../../src/player/player_save_pipeline.c) acknowledges
the player revision and related completion state; it does not refresh item
ownership entries either. Snapshot capture explicitly describes ownership
entries as potentially absent or stale between logins in
[player_snapshot_capture.c](../../src/player/player_snapshot_capture.c).
This follows the [memory-authority design](../adr/0002-persistence-reset-memory-is-the-authority.md).

Neither ordinary object extraction nor terminal character extraction clears a
player's cached item entries in
[handler.c](../../src/world/handler.c). Therefore an old holder's cache entry
can survive the physical object's movement and later unload.

### Artifact qualification consults that old cache before hydration

[`player_load_materialize()`](../../src/player/player_load_materialize.c)
first checks whether the player's body is already active, then calls
`player_load_items_qualify()` on the captured source. Artifact construction and
attachment happen afterward. Session loading hydrates its optional ownership
cache only after constructing and attaching the admitted graph.

[`artifact_owned_source_error()`](../../src/guild/artifact.c), used by
`artifact_player_source_error()`, compares captured custody with the saved
source. It then performs this additional check:

```cpp
if (item_ownership_runtime_lookup(source.item_uid, &current) &&
    (current.vnum != custody.vnum || current.state != custody.state ||
     !item_owner_identity_equal(current.owner, custody.owner) ||
     current.root_item_uid != custody.root_item_uid ||
     current.parent_item_uid != custody.parent_item_uid ||
     current.item_revision > custody.item_revision))
    return ESTALE;
```

**An older cached owner or topology fails this check even when the captured
custody has a higher item revision.** Only the final revision comparison is
directional; the owner and topology comparisons are unconditional.

The qualifier in
[player_load_items.c](../../src/player/player_load_items.c) maps that error to
`custody_or_topology_mismatch`, retains the raw source component, and removes
it from the admitted item list. Later hydration only sees the remaining items.
It cannot refresh the item that qualification just removed. Repeating the load
can repeat the same retention without changing the conflicting entry.

Clearing only the recipient's cache domain is also insufficient when the stale
entry still names an earlier player or that player's corpse:
`item_ownership_runtime_forget_player_domain(recipient)` selects entries by
their **cached owner**. The isolated probe verified this case.

The same source predicate runs again during `artifact_begin_recovery()`.
Changing only the initial qualifier would leave construction subject to the
same refusal. Any correction must address the shared admission contract.

### What this error category actually covers

`ESTALE` from the shared predicate has several possible causes:

| Comparison | Fields that can cause this alert |
| --- | --- |
| UID against artifact identity map | UID tracked under a different artifact vnum |
| Saved source against captured durable custody | UID, vnum, active state, nonzero item revision, owner type/ID/context, root, parent |
| Runtime cache against captured durable custody | Vnum, state, owner type/ID/context, root, parent, or a runtime item revision greater than the captured revision |

Missing source/canonical evidence instead returns `ENODATA`; an existing live
artifact body or pending creation returns `EEXIST`; a durably retired/rejected
identity returns `EIDRM`. These become different load outcomes. The cache check
runs before the final live-body check, so the generic mismatch category is not
proof that no competing body exists.

For the reported gloves, the inspected saved/durable fields and canonical
references agree, and durable custody has not changed since 02:57. That makes
the reproduced cache failure the strongest supported explanation. There is no
historical dump of the source result or live maps, so the exact failed field
at 11:10:43 remains unproven.

### Origin and coverage gap

Git history traces both the cache predicate and qualification-before-hydration
ordering to `53d0da2f76526b136867df98d8c2fbe02dab3176`, the October 17
artifact identity integration, “Integrate artifact identity, recovery, and
reward fixes (#184).” The later [October 18 owner-tracking investigation](https://github.com/LuminariMUD/Duris/blob/0a972227636b66c4e0c98900b1120c25ac181353/docs/ongoing-projects/2026-10-18-artifact-owner-mismatch-investigation.md)
concerned admitted artifacts with stale location/binding tracking. This failure
occurs earlier: the artifact never reaches successful attachment, so the
post-attachment tracking reconciliation cannot rescue it.

The existing admission fixture checks an owner disagreement at the **same**
item revision, a runtime revision **newer** than captured custody, and an
unrelated owner-revision advance. It does not check an **older** item revision
with stale owner/topology followed by a new owner's login. Those safeguards
can all pass while this normal handoff fails. The investigation probe adds
that missing case without weakening the newer-revision control.

## Retention preserves evidence but provides no recovery workflow

`retain_source_root` preserves the complete component connected through raw
container links or the custody-reconciled graph. A nested artifact can withhold
its container and other contents too. `first_vnum` is the first failing item
reported by this load, not necessarily its enclosing root or a count of all
affected artifacts. This incident retained only the gloves.

The character receives:

```text
Some saved items need staff review and remain in storage. Reference: player_load/retained.
```

The retained selector is stored on `ch->only.pc->retained_items` and copied into
later in-process save captures. On MariaDB, `retained_player_rows()` validates
and locks the protected component; the save deletes/replaces only other item
rows. The retained rows keep their IDs, nullable payload fields, affects, and
extra descriptions. This is why an ordinary save does not erase the gloves.

This path does not insert an `item_ownership_quarantine` row. There is no SQL
release flag to toggle. On a new load, source qualification decides retention
again. There is no periodic requalification or staff release action for the
already admitted character. Preservation alone does not return the item to play.

### Existing staff tools and their limits

| Tool or action | What it can establish or change |
| --- | --- |
| `artifact hunt <initial>` | Reads saved player sources without constructing items; reports UID, source row, canonical identity, captured custody, root, parent, and revisions |
| Hunt discovery | Enumerates legacy `Players/<initial>` filenames; it is not a database-wide player discovery command |
| Hunt output | Omits the runtime ownership entry, exact failed predicate, and live-body/pending-conflict evidence; can look consistent while login still withholds the item |
| SQL payload/custody query | Establishes durable state at query time; cannot read the process-local cache |
| `scripts/classify_item_topology.py` | Classifies saved SQL topology; cannot inspect the runtime cache. Feeding this incident's current joined row into its classifier produced no finding |
| `artifact reset sync` | Updates artifact location tracking for live objects; does not restore an unmaterialized retained item or refresh the item ownership map |
| `artifact reset syncdb` | Explicitly unavailable; requires a complete population audit |
| `artifact clear` | Requires proven physical absence; the retained canonical item is present |
| `artifact reset <vnum>` / `fixit` | Edits binding/timer state, not the ownership-cache conflict |
| Load, clone, swap, poof, or offline materialization | Not a release mechanism; creation/retirement would change the wrong state, and materialization uses the same qualification path |
| Repeated login or save | Does not reliably clear the conflicting entry; the probe reproduces repeated retention |

The staff message promises review, but the available inspection cannot show the
side of the comparison most likely to explain this incident. That is an
observability and recovery defect alongside the admission defect.

## Concrete staff triage and recovery procedure

### Collect and compare before any correction

1. Correlate the staff notice with `logs/log/artifact` and `logs/log/file` at
   the same timestamp. Record the PID, row, UID, vnum, retention count, and
   errno in restricted incident evidence. A throttled staff notice is not a
   complete list of affected items.
2. Use `artifact hunt <initial>` where the character has a discoverable legacy
   filename. Treat it as inspection. If it finds nothing, query the named
   source row directly; missing hunt discovery does not prove item absence.
3. Run the following transaction through the existing credentialed database
   connection. Replace `<source_row>` and `<vnum>` with numeric values from the
   alert. Preserve the output privately. These statements perform no repair.

```sql
START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY;

SELECT p.id, p.pid, p.obj_uid, p.vnum, p.quantity, p.equip_slot,
       p.container_id, parent.pid AS parent_pid,
       parent.obj_uid AS payload_parent_uid, p.extra_flags, p.created_at,
       o.item_uid AS custody_uid, o.vnum AS custody_vnum,
       o.owner_type, o.owner_id, o.owner_context_id, o.state,
       o.root_item_uid, o.parent_item_uid, o.item_revision, o.updated_at,
       r.revision AS owner_revision
FROM player_items p
LEFT JOIN player_items parent ON parent.id = p.container_id
LEFT JOIN item_current_owner o ON o.item_uid = p.obj_uid
LEFT JOIN item_owner_revision r
  ON r.owner_type = o.owner_type AND r.owner_id = o.owner_id
 AND r.owner_context_id = o.owner_context_id
WHERE p.id = <source_row>;

SELECT vnum, canonical_item_uid, identity_state, rejected_item_uids,
       owned, loc_type, location, timer_epoch,
       bind_owner_pid, bind_timer_epoch, updated_at
FROM artifact_domain_state WHERE vnum = <vnum>;

SELECT a.item_uid, a.old_owner_type, a.old_owner_id,
       a.old_owner_context_id, a.new_owner_type, a.new_owner_id,
       a.new_owner_context_id, a.claimed_at
FROM item_owner_audit a
JOIN player_items p ON p.obj_uid = a.item_uid
WHERE p.id = <source_row>
ORDER BY a.audit_id;

COMMIT;
```

4. For a nested item, follow the full ancestor/component graph. Check all
   relevant physical stores, canonical/rejected identity references, active
   live bodies, pending item commands, and recovery sources before asserting
   that a source is unique. Retain affects, descriptions, enhancements,
   timers, soul, and mana evidence with the item payload.
5. If durable owner, state, identity, or topology actually conflicts, escalate
   that specific conflict. The stale-cache finding is not permission to choose
   a winner between contradictory sources. If SQL agrees, record that result
   and the cache visibility gap; do not rewrite matching SQL to make an alert
   disappear.

### Restore through a fresh qualified load

There is currently **no supported targeted staff command** to perform the
necessary cache reconciliation and rerun the retained graph's admission.
Internal `item_ownership_runtime_forget(uid)` followed by a new qualification
worked in the isolated fixture. Calling it through a production debugger or
clearing whole runtime maps is not a reviewed operational procedure.

For a confirmed stale-cache-only case, the existing broad workaround is an
**owner-authorized orderly restart followed by a fresh login**, after the
normal backup, writer drain, and population checks. A fresh process discards
the stale runtime map. This is expected to admit the unchanged saved source
when no other conflict is restored; it was not exercised against production
in this investigation and is not a permanent correction. A source conflict
can survive a restart, and recovery hydration can introduce other evidence.
Staff must not promise that every retention alert is solved by restarting.

Prefer a tested admission correction deployed through the ordinary approved
release process. The affected online character will need a fresh item load;
deploying code or correcting a cache does not insert the withheld item into
its existing body automatically.

After either route, verify that the same physical UID is present exactly once,
the source is no longer retained, equipment/container placement and enhancements
match the saved item, and timer/soul/mana state is preserved subject to normal
elapsed time. Save, log out, and log back in again; verify the same result and
absence of a new alert. A normal successful save may replace the old payload
row ID, so use the physical UID to follow the item. Record the result before
closing the incident.

No restart, staff command, cache mutation, or live repair was attempted here.

## Required correction and acceptance evidence

The smallest correction belongs at the shared source-admission boundary:
distinguish obsolete cache evidence from a genuinely newer transition or
competing physical copy. A lower-revision cached owner/topology must not veto
a fully qualified newer saved source merely because it differs. Do not
globally disable custody checks or blindly hydrate the cache before source,
identity, live-copy, and pending-operation checks have established admission.
Equal-revision contradictory evidence and a cache newer than the captured
load require explicit treatment; this investigation does not establish that
they are safe to overwrite. Publish reconciliation on the game thread and
preserve failed-load rollback.

Use the same rule in prequalification and recovery construction. Reuse the
existing loader, runtime map, and writer. The solution does not require a new
item authority, a second persistence queue, or SQL in gameplay movement paths.

Diagnostics must identify which comparison failed. At the failing boundary,
record a bounded reason such as identity-vnum conflict, source/custody conflict,
runtime-owner conflict, runtime-topology conflict, or runtime-newer-revision.
The restricted diagnostic needs both source/captured custody and runtime
owner type/ID/context, root, parent, vnum, state, item revision, owner revision,
canonical UID/state, and live/pending status. Correlate this with the retained
root/component and the staff reference. Keep the staff broadcast concise and
numeric; record the detailed values at failure time, before later hydration
can change the evidence.

Extend `artifact hunt` or the existing inspection surface to show the same
runtime comparison. If manual release remains necessary for genuine data
repairs, route it through a fresh qualified load after the owner is offline
and pending work is settled, with exact preconditions and a clear success or
refusal result. Do not add a force-load bypass.

Permanent coverage should prove:

- Player A → corpse → player B → recipient → save/logout/login in one process
  admits exactly one unchanged canonical artifact despite older cache evidence.
- Same-owner container changes with older cache topology load correctly.
- A repeated failed load preserves the entire raw component and unrelated
  inventory; a corrected source is admitted on a fresh load.
- Clearing a recipient domain does not masquerade as complete reconciliation
  when the conflicting cached owner is foreign.
- Newer cache revisions, equal-revision contradictions, pending transitions,
  live canonical copies, wrong vnums, missing custody, and retired/rejected
  identities retain their appropriate safeguards and distinct diagnostics.
- Worn, carried, and nested items preserve UID, enhancements, timer, soul, and
  mana; failed construction/attachment does not publish a premature correction.
- MariaDB and flat-file load/save paths pass their applicable journeys. The
  failing admission predicate is shared, but only MariaDB production state was
  inspected here.

## Executable verification and provenance

The investigation extended the existing
[artifact creation/admission harness](../../tests/async/test_artifact_creation_admission.py)
in a scratch driver under `bin/tests/`. It links the real artifact service,
runtime ownership implementation, topology implementation, and extracted
`player_load_items_qualify()`; constructor and rollback coverage from the
existing harness runs alongside it. It uses synthetic IDs, no database,
no `.env`, and no running MUD.

The probe fixes the saved source and durable custody at player 77, UID/root
4242, vnum 900, no parent, item revision 3. Each case changes only the runtime
entry:

| Runtime evidence | Qualification result |
| --- | --- |
| No entry | One active item; no retained rows |
| Earlier player owner, item revision 1 | No active item; one retained row; repeat has the same result |
| Earlier container/root, item revision 1 | No active item; one retained row; repeat has the same result |
| Same fields, item revision 4 | No active item; one retained row; preserves the newer-revision guard |
| Earlier corpse owner, item revision 1 | No active item; one retained row; repeat has the same result |
| Foreign stale entry after forgetting player 77's domain | Entry remains; item remains retained |
| Remove only that UID's cache entry, then qualify a fresh copy of the same source | One active item; no retained rows; canonical UID, timer, and soul unchanged |

All assertions and the surrounding admission scenarios passed under
`-fsanitize=address,undefined -fno-sanitize-recover=all`. The observed false
withholding is the behavior being demonstrated; a passing probe does not
mean the production defect is fixed. The probe's targeted removal is a
diagnostic control, not a shipped recovery command.

Session-local reproduction and output:

```bash
python3 bin/tests/investigate_artifact_player_load_20261102.py
# retained output from this run:
cat bin/tests/artifact-player-load-20261102.log
```

These ignored build/test artifacts are session evidence, not permanent
regression coverage. The case matrix and fixture entry point above describe
what must be retained when implementing the correction. A full server
handoff/relogin journey, actual process restart recovery, and a repaired
implementation have not been qualified by this investigation.

The documented SQL transaction was also executed read-only with the incident's
numeric selectors and returned the matching payload, identity, and five audit
rows. All local source/document links were checked. No server build was needed
because production C/C++ source was unchanged.

Source checkout:
`0a972227636b66c4e0c98900b1120c25ac181353`. The serving process started
**2026-11-01 15:36:03 UTC**, using `bin/server/dms` from this checkout.
The executable SHA-256 is
`f78fdd1314343a104736dcfd1c47879ec631f2ee62ce72e5f09a781fe2a8f9bb`.
`bin/server/dms_new` is a separate later build and was not assumed to be the
serving binary.

Read-only disassembly of the serving executable confirmed the runtime lookup,
unconditional owner/root/parent comparisons, and branch returning `0x74`
(`ESTALE`) in `artifact_owned_source_error()` at `0x378900`. The rejecting
runtime comparison is at `0x378ccf`–`0x378d3f`. No debugger was attached to the
process. The artifact implementation and load qualifier were last changed
on October 27 and October 25 respectively, before this executable's build.
This verifies the relevant deployed predicate without assuming a full
binary-to-checkout commit mapping.
