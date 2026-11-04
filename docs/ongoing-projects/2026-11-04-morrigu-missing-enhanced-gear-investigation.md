# Morrigu: missing enhanced gear investigation

Investigated on production on November 4, 2026; database state rechecked at
13:26 UTC. All times below are UTC.
The supplied 15:06–15:11 chat matches server chat at **13:06–13:11**.
Character PID: **234**. Account locker: **41**,
`account.morrigu.1.locker`; its public chest is also ID **41**.

## Finding

**One earring has a confirmed, unexplained disappearance from Morrigu's saved
equipment on November 3. The retained evidence does not establish a simultaneous
loss of three earrings and gloves.** The engineering review below independently
reproduces SQL item-property loss and an enhancement-cap bypass. Those defects
retain the item's UID and do not establish the cause of this earring's disappearance.

- The two earrings formerly in the locker were withdrawn by **Morrigu**, with
  explicit chest GET records, on November 3 at 14:06:52 and 14:06:54. Both then
  appear in Morrigu's saved ear slots. Their absence from the locker today has
  an evidenced explanation.
- One of those earrings, UID **112150098**, is present at **15:59:31** on
  November 3 and absent from the **16:07:40 rented save**. It is the only item
  UID removed between the two saved inventories. Its exact removal mechanism
  remains unproven.
- The other, UID **112150076**, remains equipped and saved today.
- An earlier earring, UID **112092122**, was looted from Morrigu's corpse on
  November 2 and subsequently passed between other characters. It currently
  belongs to Cua. This is a separate, recorded loss.
- A fourth Morrigu earring and the reported hands of justice could not be
  assigned saved identities from the records examined. That is an evidence gap,
  not proof that Morrigu never had them.
- The last positively identified hand-slot item is a different pair:
  **fingerless gloves of su-monster skin**, vnum **67259**, UID **110027424**.
  The Nov 1 23:15:37 save has them equipped. On Nov 2 they enter Morrigu's
  corpse, are claimed by Rani, then Iko; their current canonical identity and
  saved hand-slot payload name Iko. This also has a recorded PvP history.

The forensic investigation and engineering review are complete for the evidence
available here; the cause of UID 112150098's loss and the gloves report remain
unresolved. **This pass is research, write-up and planning only. No application
fixes were implemented.** No restoration, deployment, production migration,
player-data edit or production restart was performed. Production SQL sessions
were set to `TRANSACTION READ ONLY`; backup archives and logs were read without
modifying them. The deliverable is this report. Disposable test programs and
logs are ignored artifacts under `bin/`; test databases contained synthetic data
in temporary local containers. Unrelated worktree changes were preserved.

## Earring identities and timeline

All three identified earrings are **vnum 98961**, a pulsating gemstone earring.
The retained item-affect rows for both locker earrings contain
`APPLY_WIS_MAX` (34) **+2** and apply location 20 **−1**. Their saved extra flags
are **8256**, including `ITEM_NOREPAIR` and `ITEM_FLOAT`, without `ITEM_NORENT`.
They have distinct UIDs; these records are not two copies of one UID.

| UTC | Evidence |
| --- | --- |
| Nov 1 17:47:59 | Status log: Morrigu enhanced an item into vnum 98961. The 23:16 native backup saves UID 112092122 in ear slot 22. |
| Nov 1 23:55:34, 23:55:51 | Status log: two further successful enhancements into vnum 98961. Ownership rows for UIDs 112150076 and 112150098 name locker/chest 41 from 23:55:55. |
| Nov 2 02:44:25–02:55:02 | UID 112092122 moves from Morrigu to corpse 1006815934729, then Grutan (245), Rani (229), and Cua (233). Corpse log independently records Grutan looting a gemstone earring from Morrigu at 02:44:31. |
| Nov 2 14:31 and 23:40 backups | UIDs 112150076 and 112150098 are both saved in locker/chest 41. |
| Nov 3 14:00 website backup | Both earrings are still saved in locker/chest 41, rows 142621–142622. This is the latest locker snapshot confirmed in the follow-up check. |
| Nov 3 14:06:52 | `private_chest_log` row **1960**: Morrigu GET, UID **112150098**, locker/chest 41. |
| Nov 3 14:06:54 | `private_chest_log` row **1961**: Morrigu GET, UID **112150076**, locker/chest 41. |
| Nov 3 14:07:17 | `item_owner_audit` rows **77699–77700**: those two UIDs change from locker `5:41:41` to player `1:234:0`. |
| Nov 3 14:52:32, 15:55:25, 15:59:31 saves | Both UIDs are saved on Morrigu: 112150098 in slot **22**, condition **99**; 112150076 in slot **23**, condition **100**. Both timers are 0. |
| Nov 3 16:07:40 | `log_entries` row **26177** records “Rented Out” at room **28283**. The corresponding saved inventory contains 112150076 but no 112150098. |
| Nov 3 16:57 and Nov 4 01:05 backups | The 16:07:40 payload already lacks 112150098. Its active player ownership row still exists in the 16:57 backup, but is absent by the 01:05 backup. |
| Nov 4 13:04:12 | Morrigu enters the game; the complaint follows at 13:06. The confirmed loss therefore predates this login and today's 10:41 restart. |

The chest action interpretation is defined in
[`src/sql/sql_player.h`](../../src/sql/sql_player.h): action **4** is
`CHEST_ACTION_GET`. These are withdrawal records, not identification messages.
All retained chest-log rows for locker 41 name Morrigu; there is no recorded
other-character withdrawal in that table. This does not establish who controlled
the client or independently prove account security.

UID 112092122's complete audit chain also includes Cua's later corpse/recovery
transitions. Its current row and player payload name **Cua**, PID 233, ear slot
22. It should not be copied back to Morrigu as though it were an unclaimed item.

## What is actually missing

The website's **16:00** and **17:00 November 3** database backups provide the
tightest before/after pair. Morrigu has **87** item rows in the former and **86**
in the latter. Comparing by UID, there are **no added UIDs** and exactly one
removed UID: **112150098**. All other saved equipment UIDs and slots match.
The before row has condition 99 and timer 0; the after inventory is stamped
16:07:40. **15:59:31–16:07:40 is the saved-record interval**, not a proven exact
gameplay-removal interval. `player_items.created_at` defaults to the database's
current timestamp, and the writer does not supply capture time. Queue delay can
separate the represented live state from that timestamp. The evidence does not
distinguish gameplay removal from omission during terminal capture/write.

At investigation time, UID 112150098 has no payload in any of
`player_items`, `locker_items`, `account_locker_items`, `corpse_items`,
`saved_items`, `player_pet_items`, `shopkeeper_items` or `siege_items`. It also
has no current ownership row or item-transfer ledger event. Its only ownership
audit event is the November 3 locker-to-player claim.

The likely gloves prototype is **38726**, “the hands of justice,” with base
wisdom maximum +3 and constitution maximum +3. It is a distinct object from
the swords called “the two hands of justice” (29265/91465). None of these three
vnums appears in Morrigu's player or locker payloads in the sampled native
backups: Nov 1 23:16; Nov 2 14:31 and 23:40; Nov 3 14:55, 15:56 and 16:57.
The 16:00 and 17:00 website snapshots already have no item in the hand slot.
No current payload for vnum 38726 was found in the eight stores listed above,
and no `item_owner_audit` row exists for that vnum. A UID or dated earlier
inventory is needed to turn this part of the report into a traceable incident.

The base prototype is defined in
[`areas/obj/nyneth3.obj`](../../areas/obj/nyneth3.obj). It is `ITEM_WORN`, wearable
on hands, with material **19 (adamantium)**, weight **3**, initial condition
**100**, craftsmanship **12**, `ITEM_GLOW` and `ITEM2_MAGIC`. All eight value
fields are zero; its two fixed affects are wisdom maximum +3 and constitution
maximum +3. Its description calls the gloves gold chainmail, but the coded
material is adamantium. The object definition contains no fixed ingredient
list, and these base properties do not establish Morrigu's enhanced version.

The last confirmed hand-slot payload is instead native Nov 1 23:16 backup row
**9064976**: vnum **67259**, UID **110027424**, equip slot **10**, saved
23:15:37. The Oct 31 snapshot has generated **soldier's stone talons**, vnum
1252, UID **109208481**, in slot 10. Audit rows **58337**, **58446**, **58796**
trace the su-monster gloves from Morrigu to corpse 1006815934729 at Nov 2
02:44:25, then Rani at 02:44:53 and Iko at 02:57:53. The artifact log records
binding to Iko at 03:00:41. The current canonical UID remains 110027424 and
Iko's saved payload has it in slot 10. This identifies previously worn gloves;
it does not identify the separately reported hands of justice.

### Follow-up: hand gear beside the locker earrings

The **November 3, 2026 14:00 UTC** website backup still contains both earrings
in locker 41, about seven minutes before their logged withdrawals. The archive
is `/home/staging/durisweb-backups/duris-hourly-2026-11-03-140000-0523245a-86c4-4bd4-8cdd-9824da37596e.zip`,
member `database/database.sql`.

All **48** saved locker item rows were checked. Every row has explicit wear
flags; exactly two have `ITEM_WEAR_HANDS` (128):

| Saved name | Vnum | UID | Saved fixed affects | Condition |
| --- | --- | --- | --- | --- |
| some soldier's stone talons | 1252 | 109208481 | +3 wisdom, +4 hitroll | 98 |
| some blood-stained iron claws | 1252 | 112099659 | +2 constitution maximum | 100 |

Both are generated items sharing vnum 1252, with different UIDs and custom
names. Neither is the hands of justice (38726), and neither has a saved wisdom
maximum affect. No other hand-slot gear is present in that locker snapshot.
The talons are the same UID seen equipped in the October 31 player snapshot.

## Persistence and enhancement checks

The current code preserves item identity by UID, not by vnum. In
[`player_snapshot_capture.c`](../../src/player/player_snapshot_capture.c),
`capture_items()` visits every equipment slot and captures each object tree;
its cycle guard uses object pointers. The SQL claim path in
[`item_claim_repository.c`](../../src/item/item_claim_repository.c) also keys
items by UID. Merely wearing two vnum 98961 objects does not select one for
removal in these paths. In fact, the historical database snapshots demonstrate
that both earrings were saved together repeatedly, including across a login.

A disposable C++ check linked the actual current snapshot capture and codec
implementations with inert engine stubs. It placed two distinct vnum 98961 UIDs
in slots 22/23, using the observed flags, conditions and wisdom affects, plus
a synthetic vnum 38726 object in the hand slot. **RENT_INN, RENT_CRASH and
RENT_CAMPED all retained all three identities, slots and tested affects through
encode/decode.** Source and executable are ignored local artifacts under
`bin/tests/morrigu-investigation/`; `verification.log` records the result.
This checks capture
and serialization only; it is not a reproduction of the historical loss, a SQL
writer test, or a complete gameplay/restart journey. No test server connected
to production and no production build or service was replaced.

The legacy replacement enhancement in
[`enhance.c`](../../src/item/enhance.c) creates a new object, marks it
`ITEM_NOREPAIR`, and extracts the source/material. That explains the changed
UIDs when enhancement creates an earring. The two saved locker earrings do not
carry `ITEM_NORENT`, so the ordinary rent exclusion does not explain their
observed payloads. There is no matching successful replacement enhancement,
sale, corpse-loot or PvP destruction status entry for the missing earring in
the bounded November 3 interval. No Morrigu death was found in that interval.
These are bounded negative log checks, not proof against unlogged extraction.

One concrete gameplay alternative is NPC theft:
[`specials.c`](../../src/mob/specials.c), `npc_steal()`, can select a worn ear
slot, unequip the item and give it to the NPC. Successful undetected theft
does not notify the victim, and this path does not log ordinary stolen items
by UID. It can therefore produce this general evidence pattern. Morrigu's
route and the responsible NPC, if any, are not retained, so **NPC theft is a
candidate, not a finding of cause**.

The missing ownership row today does **not** identify the original cause.
[`handler.c`](../../src/world/handler.c), `extract_obj()`, deliberately leaves
ordinary extracted items' ownership rows behind. The boot reaper in
`item_claim_repository.c`, `reap_unheld_player_items()`, deletes eligible player
ownership rows only after their payloads are gone. The 16:57 backup has exactly
that intermediate state: active owner row, absent player payload. Reaping is
consistent with the later row disappearance, and cannot explain the earlier
payload loss by itself.

## Engineering review and concrete fix plan

Reviewed November 4 against checkout
`af3829b85671480cdae23ae703da6ed1ca50a11a` and fetched `origin/master`
`264c4879114a03fdf33169a57466c4f14de24101`. The capture, SQL item writer,
player SQL loader, materializer, enhancement and NPC-theft source files cited
below are identical between those revisions. The newer copyover change is
accounted for separately. No checkout, deployment or application edit was made.
Source line numbers refer to the investigated checkout.

Before publication, master was rechecked at
`49fabec2c33c288b2059aed8735ae03b20828631`. The intervening changes touch tests;
there are no source or migration changes from the earlier checked master.
Actionable repairs are now tracked in
[issue #682](https://github.com/LuminariMUD/Duris/issues/682).

Priorities describe proposed engineering work, not proof of incident causation.

| ID / priority | Finding and confidence | Relationship to this incident |
| --- | --- | --- |
| R1 / P1 | Reproduced: SQL treats fixed item affects as a deduplicated list, losing both additive bonuses and reserved slot positions. | Can weaken enhanced items or let them exceed the enhancement cap; does not remove their UID. |
| R2 / P2 | Reproduced: SQL omits permanent per-instance item fields that capture/codec preserve. Runtime consequences are supported by source inspection. | Can change enhanced/crafted/generated item behavior after reload; does not explain the missing UID. |
| R3 / P2 | Reproduced with controlled engine boundaries: ordinary NPC theft has no UID audit or victim notification in the tested successful cases. Other removal/replacement diagnostics also lack the identity chain. | Leaves a plausible removal route untraceable; no evidence identifies a thief or proves theft occurred here. |

### R1: preserve fixed-affect multiplicity and slot identity

The representation is a four-slot array, and gameplay gives those slots meaning:

- [`player_snapshot_capture.c`](../../src/player/player_snapshot_capture.c),
  lines 428–474, captures each fixed affect at its original index.
- [`player_snapshot_repository.c`](../../src/player/player_snapshot_repository.c),
  `insert_item_rows()`, lines 550–617, drops zero slots and deduplicates identical
  `(location, modifier)` pairs. SQL stores no slot index. This shared writer is
  used for player, pet, locker, corpse, shopkeeper and saved-room items.
- [`player_load_repository.c`](../../src/player/player_load_repository.c),
  lines 1038–1105, deduplicates again and packs surviving rows into successive
  array slots. Its pet loader has the same pattern.
- [`sql_player.c`](../../src/sql/sql_player.c), `sql_set_item_affects()` at
  line 1032, also drops duplicates and compacts rows; locker loading uses it.
- [`affects.c`](../../src/magic/affects.c), lines 1544–1548, applies every fixed
  slot. Equal bonuses are additive. [`enhance.c`](../../src/item/enhance.c),
  `modenhance()` at lines 989–1020, stores essence improvements specifically in
  `affected[2]` and enforces `enhance_mod_max_steps` using that slot's modifier.
- The database also enforces the wrong identity: immutable migration
  [`0002_player_item_metadata_uniqueness.sql`](../../migrations/immutable/0002_player_item_metadata_uniqueness.sql)
  deduplicates player/pet affects and adds unique `(item_id, location, modifier)`
  keys. Removing only the C++ deduplication would encounter those constraints.

Two executable reproductions use the real `modenhance()` body, capture, codec,
SQL writer and repository loader against disposable MariaDB:

| Fixture | Before save | After SQL load / next enhancement |
| --- | --- | --- |
| Vnum 98961, base WIS_MAX +2 and saving paralysis −1; apply two WIS_MAX essences (400251) | Fixed slots `(34,+2), (20,−1), (34,+2), (0,0)`; total item WIS_MAX **+4** | One equal pair disappears; total **+2**, same UID. |
| Generated vnum 1252, base CON_MAX +2, empty slot 1; apply three WIS_MAX essences | Slots `(35,+2), (0,0), (34,+3), (0,0)`; essence cap **3** | The +3 moves from slot 2 to slot 1. Another real `modenhance()` call adds +1 in now-empty slot 2: total essence WIS_MAX **+4** despite cap 3. |

The second fixture models a sparse generated item, not a claim that Morrigu
applied these essences to the locker claws. The historical earring rows do not
establish either essence sequence. Both reproduced failures retain identity.

**Proposed repair:** make slot index, rather than affect value, the identity in
SQL. Add nullable `affect_slot` to the affected active item-affect tables in a
new guarded migration; replace the conflicting player/pet value-based unique
keys with uniqueness on `(item_id, affect_slot)`. Preserve the sealed migration
0002 and its checksums. Write all four indexed slots, including explicit zeros,
so an intentionally cleared array also overrides prototype bonuses correctly.
Load indexed rows into their exact slots without value deduplication. Update
the shared writer and each consuming loader together; check other active item
stores before claiming parity. Keep a documented legacy path for old NULL-slot
rows, whose original multiplicity and positions cannot be recovered reliably.

Do not sum equal locations as a shortcut: the reserved enhancement slot would
still be lost. Do not infer or reimburse erased bonuses from current rows alone.
Qualify migration and loader changes together; an old writer can still discard
new slot information, so a binary downgrade is not automatically lossless.

**Acceptance criteria for implementation:** both examples above preserve exact
arrays and UIDs after SQL reload; the fourth essence is rejected without
consuming materials/money; all-zero arrays, negative modifiers, equal bonuses
and holes survive. Cover player/pet, locker, corpse, shop and saved-room paths,
legacy NULL-slot rows, migration reruns and SQL transaction rollback. Retain
the distinct-UID/same-vnum test and compare with the existing complete snapshot
backend. A codec-only test is insufficient.

### R2: persist permanent item fields beyond the primary flags

Capture at `player_snapshot_capture.c:439–464` includes `extra2_flags`,
`anti_flags`, `anti2_flags`, `craftsmanship` and all timers. The SQL insert at
`player_snapshot_repository.c:562–588` includes none of those flags or
craftsmanship, and only `timers[0]`. The probe confirms `ITEM2_ENHANCED`
**262144 → 0** in the returned repository snapshot; synthetic anti flags 5/6,
craftsmanship 42 and timer 1 value 123 are also absent after reload.

This is not a claim that every live loaded object gets zero for these fields.
`player_load_items.c:694–708` leaves them at prototype values when
`complete_snapshot_state` is false, as the player SQL entry point at line 1195
requests. Consequently, per-instance differences are lost. Relevant real
producers/consumers include:

- `modenhance()` sets `ITEM2_ENHANCED` on the instance.
- [`crafting.c`](../../src/economy/crafting.c), lines 918 and 1495, sets
  `ITEM2_CRAFTED`. [`actobj.c`](../../src/cmd/actobj.c), line 4310, relies on
  that flag to prevent giving crafted/forged objects to NPCs. If the prototype
  lacks the flag, the SQL round trip loses that restriction.
- [`tradeskill.c`](../../src/economy/tradeskill.c), line 346, adds recipe-specific
  class restrictions through `anti_flags`.
- [`random_equipment.c`](../../src/item/random_equipment.c), line 442, sets
  generated-item craftsmanship independently of the base prototype.

The field omissions were executed; the crafted-item give and class-restriction
consequences were traced in source, not tested through a running game.
Secondary timers are a representation difference requiring a lifecycle review,
not evidence that every temporary timer or dynamic spell effect must persist.

**Proposed repair:** persist and restore the permanent instance flags and
craftsmanship through the existing item snapshot path, using nullable SQL fields
to distinguish legacy absence from an intentional zero. Apply them in every
affected loader. Do not simply set `complete_snapshot_state=true` for old SQL
rows: default zeros would overwrite valid prototype state. Decide separately
which timers and dynamic effects are intended to survive logout/restart.

**Acceptance criteria:** crafted and enhanced flags, changed class restrictions,
craftsmanship and intentionally cleared flags survive the relevant save/load
paths; the NPC give restriction behaves the same before and after reload.
Legacy absent fields retain prototype fallback. Add SQL-versus-complete-snapshot
comparisons for permanent fields, plus actual materialization and gameplay
checks rather than checking only the repository snapshot.

### R3: log successful ordinary-item removals with stable identities

`npc_steal()` in [`specials.c`](../../src/mob/specials.c), lines 247–398,
can take worn ear and hand slots. The success branch's only status log is
inside `IS_ARTIFACT(obj)`, but the earlier artifact check already makes that
attempt fail. It therefore supplies no ordinary-item theft audit.

A disposable ASan/UBSan executable ran the unmodified function body with
controlled visibility, movement, carry and output boundaries. With level-31
thief/victim, ordinary zero-weight gear and a successful roll, both ear slots
and the hand slot were tested against every detection roll −60 through 100:
**483 successful removals, all retaining the UID, with no victim notification
or audit log from the function.** This is a function-level reproduction, not
a recreation of Morrigu's route or the full object movement/persistence stack.

The arithmetic also deserves an explicit balance decision: success requires
`percent > 175`; then weight is subtracted. For weight at most 76, the result
stays at least 100, so `MIN(100, percent) < number(-60, 100)` cannot detect the
successful theft. That may be intentional stealth behavior. Auditing it does
not require changing success odds or notifying the victim.

Related forensic gaps: replacement-enhancement logs identify the result's
vnum/name without linking source and result UIDs; ordinary damage/destruction
messages do not provide a durable UID/reason trail. The player capture trace
(`player_save_pipeline.c:464`) records PID, revision and intent, not item UID
membership. These gaps prevent a reliable removal-to-save reconstruction.

**Proposed repair:** add concise records at confirmed theft, enhancement
replacement and irreversible-destruction boundaries. Record UID/vnum, holder
PID or NPC identity, room, source/destination slot and reason; enhancement needs
both source and result UIDs. Copy identity fields before extraction. Ordinary
logout teardown must not be labeled item destruction. Reuse the existing bounded
asynchronous [`persistence_log_submit()`](../../src/persistence/persistence_log.h)
path, which already reports rejection/file-failure counters. Do not introduce
synchronous per-item SQL or revive the retired persistence journal. These are
best-effort diagnostics, not a guarantee of crash-durable event history.

**Acceptance criteria:** successful ordinary theft produces one usable identity
record, failed theft produces no success record, replacement links both UIDs,
and genuine destruction records its reason once. Normal save/logout produces
no false destruction. Queue saturation remains nonblocking and visible in drop
metrics. Staff can correlate a controlled theft and following rent by UID.

### Additional gaps, decisions and ruled-out explanations

**Ordinary terminal-save rejection needs a policy decision.**
`persistence_save_character_terminal()` in
[`actoth.c`](../../src/cmd/actoth.c), lines 2134–2164, reports capture/queue
rejection but still returns true. The inn in
[`specs.room.c`](../../src/specs/specs.room.c), lines 368–395, tells the player
their gear was stored and extracts the character. A rejected latest capture
can therefore leave only an older save. This is source-confirmed behavior,
not an injected failure reproduced here, and does not explain why the observed
successful rented payload lacks exactly one UID.

[ADR 0002](../adr/0002-persistence-reset-memory-is-the-authority.md) deliberately
keeps departure nonblocking. A future change should first decide whether to
retain a failed terminal capture for recovery, adjust the departure message,
or accept the existing loss window with better alerts. Fault-inject capture
limits and queue rejection before choosing a repair; do not add blocking waits
or a second persistence architecture as an incidental fix.
[PR #656](https://github.com/LuminariMUD/Duris/pull/656) already adds an
acknowledged copyover save on fetched master. It does not change this ordinary
rent helper. The “Rented Out” log itself is a command record, not a commit receipt.

**Ordinary NPC inventory is not universally durable.**
[PR #660](https://github.com/LuminariMUD/Duris/pull/660) preserves ordinary items
on eligible unmarked roaming NPCs of vnum 1255 through Redis world recovery.
It does not cover every NPC. This environment currently has
`REDIS_WORLD_STATE=FALSE`; its exact historical value was not established.
The eight SQL stores checked above do not inventory every live NPC or every
floor object. General NPC custody persistence would be a separate product and
lifecycle decision, not a presumed fix for this incident. Any restoration must
recheck live as well as durable holders.

**Empty legacy tables are not evidence of a failed logger.**
ADR 0002 explicitly retained unused event-log schema to avoid an unnecessary
migration. No live writer for `persistence_item_events` was found. The useful
locker action trail here is `private_chest_log`, which contains both actual GET
records; legacy `locker_activity_log` is not a substitute for it.

**The boot reaper does account for the other payload stores.** Its direct SQL
query is not the whole protection: `comm.c:225–246` passes
`population.retained_uids`, collected by
[`artifact_population_repository.c`](../../src/guild/artifact_population_repository.c)
and [`artifact_population_boot.c`](../../src/guild/artifact_population_boot.c)
from all eight physical payload domains. There is no supported finding here
that account-locker, shopkeeper or siege rows are ignored by the boot call.

**Current source is not the historical binary.** The relevant November 3
uptime's status log begins at 15:33:11; Morrigu enters at 15:34:29. No exact
binary/commit marker was identified. The November 3 `deployment_log` query
returned no rows, which cannot exclude a manual deployment. If build identity
is not already emitted by the operational startup path, include it with a
stable boot identifier in the diagnostic work.

### Validation performed and its limits

| Check | Result | Limit |
| --- | --- | --- |
| Actual capture + codec, two same-vnum earrings and hands, three rent intents | Passed: all three UIDs and tested values retained. | Inert engine boundaries; no SQL or gameplay journey in this initial check. |
| Existing `run_player_save_claim_mysql.sh`, MariaDB 11.8 | Passed save/claim, load-filter, rent/replay/recovery, rollback and large zone-story legs. | General integration coverage does not exercise equal fixed affects or holes. |
| Extended actual capture → codec → SQL writer → repository loader, three rent intents | Passed baseline identities/slots/conditions; reproduced R1 and R2. | Synthetic objects, boundary stubs; no full login materialization or server restart. |
| Extracted actual `modenhance()` with SQL round trip | Reproduced +4→+2 item bonus and cap-3→+4 bypass. | Eligibility/value/naming/material-consumption boundaries stubbed; real affect mutation/cap logic. |
| Extracted actual `npc_steal()` under ASan/UBSan | 483 asserted removals without function-level audit/victim notice; no sanitizer report. | Controlled success conditions and stubbed movement; no historical route or general theft-rate claim. |

Executed commands (from the repository root):

```bash
PLAYER_SAVE_CLAIM_DB_IMAGE=mariadb:11.8 bash tests/async/run_player_save_claim_mysql.sh
python3 bin/tests/morrigu-investigation/build_sql_review_probe.py
bash bin/tests/morrigu-investigation/run_sql_review_probe.sh
python3 bin/tests/morrigu-investigation/build_npc_review_probe.py
```

The probe sources/executables and `verification.log`, `sql-review-verification.log`
and `sql-review-probe.log` are ignored investigation artifacts, not maintained
regression tests. The SQL probe refuses to run without `ENVIRONMENT=test` and
database `morrigu_gear_review`; its runner starts a disposable container and
does not load production `.env`. Temporary containers were removed after the
runs. No full game build, live gameplay journey, production fault injection or
production migration was performed. Before implementing repairs, promote the
specific fixtures above into focused maintained regression tests.

### Existing work and proposed implementation order

- [Issue #646](https://github.com/LuminariMUD/Duris/issues/646) is open for
  replacement enhancement selecting a lower-iVal result. That is a separate
  selection/upgrade defect; it does not cover R1's SQL round trip. Coordinate
  enhancement acceptance tests with it rather than filing a duplicate.
- [Issue #490](https://github.com/LuminariMUD/Duris/issues/490) / merged
  [PR #497](https://github.com/LuminariMUD/Duris/pull/497) cover earlier private
  chest access/audit work. The actual GET records here should be used rather
  than treating locker withdrawal logging as entirely absent.
- [Issue #564](https://github.com/LuminariMUD/Duris/issues/564) / merged
  [PR #581](https://github.com/LuminariMUD/Duris/pull/581) cover locker shutdown
  preparation/recovery. They do not establish ordinary player terminal-save
  acceptance or full item-property fidelity.
- [Issue #583](https://github.com/LuminariMUD/Duris/issues/583) and its merged
  artifact fixes concern artifact ownership/cache behavior. The recorded
  su-monster-glove PvP chain and this ordinary earring are distinct cases.
- [Issue #677](https://github.com/LuminariMUD/Duris/issues/677), checked before
  publication, covers encrust replacement losing guild-store buyer binding.
  That replacement defect is distinct from R2's SQL instance-field loss.
- Searches of related issues/PRs found no covering repair for R1–R3. This is a
  bounded search, not an assertion that every historical discussion was read.
  The research pass created no issue or PR. On the subsequent request to
  publish the report and create an actionable issue,
  [#682](https://github.com/LuminariMUD/Duris/issues/682) was opened with the
  three repair areas, source evidence and acceptance criteria. Application
  fixes, production changes and player restoration remain outside this pass.

Proposed work, all still **unimplemented**:

1. **R1:** add regression fixtures, then slot-aware schema/writer/loaders as one
   qualified change. Validate fresh and upgraded schemas, restarts and legacy
   compatibility before any production migration.
2. **R2:** add permanent-field persistence and actual load/gameplay checks;
   keep timer/dynamic-effect policy separate from proven permanent-field loss.
3. **R3:** add targeted UID diagnostics and correlate a controlled removal with
   its following save. Keep the theft balance decision separate.
4. Decide terminal-save rejection and broader NPC recovery policy using focused
   failure tests, as separate work from the item-property repairs.

Future C/C++ changes should receive the repository's changed-line formatting
check, `make -C src`, focused executable tests and the relevant persistence
journeys. Passing those checks would qualify an implementation; this review
does not itself authorize or claim a production rollout or player restoration.

## Evidence limits and next actions

- `persistence_item_events` is intentionally unused. No `item_ownership_ledger`
  event exists for UID 112150098. `item_owner_audit` records ownership claims, not every
  destruction, drop or in-memory move. There is no durable extraction reason
  for this UID.
- The surviving `cmd.debug` for the relevant uptime holds only the last part
  of that uptime, around November 4 00:09–00:11, not November 3 16:00. The
  latency log is aggregate timing, not an item/command transcript. No Morrigu
  web terminal session was found. MariaDB reports binary logging **OFF**.
- No restore record since November 1, deployment record in the bounded loss
  interval, or admin-action record in that interval was returned by the
  corresponding database queries. These tables cannot rule out direct actions
  outside their logging paths.
- Current-code checks cannot certify the exact historical live state. The
  checkout and fetched-master revisions, executed SQL/function tests and
  historical binary gap are recorded in the engineering review above.

The next useful evidence is Morrigu's client transcript around **November 3
15:59–16:08 UTC**, including earlier activity to allow for save delay,
particularly equipment removal, travel, NPC interactions,
destruction messages and the rent command. For the gloves/fourth earring, get
the last known date and displayed item name or a saved UID. Do not attribute
them to this same event solely because they were noticed together.

The review has now exercised the SQL round trip and identified independently
actionable property-persistence defects. A full isolated travel/removal → rent
→ login journey remains useful for investigating whole-item disappearance.
Neither the property defects nor the NPC-theft probe establishes the missing
UID's cause. Keep UID ownership checks intact and use the targeted diagnostics
proposed above to distinguish future removal events from save/load omissions.

An owner-authorized recovery could use UID 112150098's before payload and
affect rows after rechecking live and durable holders for duplication. There
is enough backup data to reconstruct that one item, but not enough evidence
to promise a correct four-item reimbursement. No recovery is included here.

## Evidence locations and repeatable reads

- Chat: `logs/log/chat`, November 4 13:06–13:13.
- Enhancement/corpse history:
  `logs/old-logs/2026.11.02-16.06.50/status` (17:47:59 and
  23:55:34/23:55:51 on Nov 1), and its `player-log/corpse`
  (02:44:31 on Nov 2).
- Loss-interval logs: `logs/old-logs/2026.11.04-00.11.39/`.
- Website before archive:
  `/home/staging/durisweb-backups/duris-hourly-2026-11-03-160000-bfc1e04d-130e-4f67-a96a-c7ca9f12608f.zip`.
  Before player row **11369461** identifies UID 112150098, PID 234,
  vnum 98961, slot 22, condition 99, flags 8256, saved 15:59:31.
- Website after archive:
  `/home/staging/durisweb-backups/duris-hourly-2026-11-03-170000-fb714208-4646-4ad8-92c2-c830f4ce58f7.zip`.
  Remaining earring row **11379016** identifies UID 112150076, slot 23,
  saved 16:07:40. Each archive contains `database/database.sql`.
- Native backup generations under `/home/staging/backups/duris/generations/`:
  `01793629869704269391-d438642fa08647448881c23c8013ecfc` (Nov 2 14:31),
  `01793662810814673954-66e1c6c0606047a4aa66eceba09c1134` (Nov 2 23:40),
  `01793717711276176577-d7b9d138fedf4526a033cbbeb9e4bcf3` (Nov 3 14:55),
  `01793721371278278945-1d75c60c84a14d528fd91e55c3fce0dc` (Nov 3 15:56),
  `01793725030637857173-59ccc725ad494e4cb187f9baad602f6d` (Nov 3 16:57),
  `01793754311267459609-13493b5f684447d8af81a8cdd668ce1e` (Nov 4 01:05).
  Read `database.sql.gz` without importing it into production. These backups
  are subject to normal retention; the historical observations above record
  what was present when examined.

Use the existing `.env` connection configuration without printing credentials.
Useful SQL, in a read-only transaction:

```sql
START TRANSACTION READ ONLY;
SELECT item_uid, vnum, old_owner_type, old_owner_id,
       old_owner_context_id, new_owner_type, new_owner_id,
       new_owner_context_id, claimed_at
FROM item_owner_audit
WHERE item_uid IN (112092122, 112150076, 112150098)
ORDER BY audit_id;

SELECT id, locker_id, chest_id, char_name, action_type, item_short, logged_at
FROM private_chest_log
WHERE id IN (1960, 1961);

SELECT id, pid, vnum, obj_uid, equip_slot, container_id,
       timer, extra_flags, item_condition, created_at
FROM player_items
WHERE pid = 234 AND vnum IN (98961, 38726);

SELECT id, locker_id, chest_id, vnum, obj_uid, container_id
FROM locker_items
WHERE locker_id = 41 AND vnum IN (98961, 38726);
ROLLBACK;
```
