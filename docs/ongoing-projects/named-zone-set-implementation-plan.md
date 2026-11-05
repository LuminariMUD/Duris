# Named zone sets: end-to-end implementation plan

Status: implementation in progress; five focused implementation PRs are pushed
and ready for review in the stack below.
Date: 2026-11-05.
Issue: [#706 — Extend named random equipment set bonuses to all eligible zones](https://github.com/LuminariMUD/Duris/issues/706).
Working branch: `branch/named-zone-set-historical-origins`, based on
`branch/named-zone-set-effect-ownership`.
Initial inspected source baseline: `2d2a7d48dea91dbe773701790239db76f59806c2`.

## Current handoff (2026-11-05)

**Review stack:** [PR #714](https://github.com/LuminariMUD/Duris/pull/714)
(`branch/named-zone-set-expansion`, `67c7fc7d9`) contains the catalog foundation
and the original planning documents.
[PR #717](https://github.com/LuminariMUD/Duris/pull/717)
(`branch/named-zone-set-origin`, implementation commit `ac527a659`) contains the
persistent-origin chunk and targets the foundation branch.
[PR #720](https://github.com/LuminariMUD/Duris/pull/720)
(`branch/named-zone-set-membership`, implementation commit `67d7ff485`) contains
worn membership and HP cleanup and targets the origin branch.
[PR #722](https://github.com/LuminariMUD/Duris/pull/722)
(`branch/named-zone-set-effect-ownership`, implementation commit `a0aebad6a`)
contains affect provenance and shared support and targets the membership branch.
[PR #723](https://github.com/LuminariMUD/Duris/pull/723)
(`branch/named-zone-set-historical-origins`, implementation commit `63160d454`)
contains the historical Misty Vale correction and targets the provenance branch.
All five PRs are ready for review; no implementation PR has been merged and no
release has been performed.

The stack includes upstream `master` through `d4b3469c0` (#711 and #721), merged
into the foundation and propagated through each dependent branch without
rewriting history. PR #721 adds inert #150 metadata for retired Misty Chasm
prototypes, with no rooms or resets; it does not add a playable set candidate.
The playable Misty Vale remains #3000 in the 104-zone assignment roster. Use the
current area registry for the remaining wider eligibility review, keeping the
initial inventory counts distinct from the final reviewed denominator.
History check: `c79fde573^:areas/zon/mist_chasm.zon` gives retired #150 the
same normalized title as new #3000. The historical-origin correction after #722
keeps unmarked Misty Vale gear from inheriting #3000's newly assigned effect by
guessing; see the checkpoint below.

The first implementation chunk extracts the **115 existing loaded set rows,
206 tiers, and 64 effect IDs** into `src/item/named_sets.c`. No expansion rows
have been installed. All **117 historical roaming rows**, their ordering and
race lists (including empty lists and stale #30/#250), remain in
`src/world/random.mob.c`; its selection function is unchanged.

Worn spell lookup, `test randomzones`, and the single named-report formatter now
read that catalog. Reports include virtual zone IDs and grow with their content;
Redis and fallback output use the same formatter. The staff dump traverses the
whole catalog and closes its file. Boot invalidates the named report before
warming it. Full-world boot validates zone IDs, duplicates, nonempty definitions,
numeric piece bounds, and supported registered handlers; mini-world boots skip
this full-world check because their fixtures intentionally omit most zones.
The application entry point also rejects unsupported handlers.

**Ablation:** reuse the current report-cache owner and existing cache lifecycle;
no second renderer, registry service, schema, effect adapter, or spawn selector
was added. The extracted catalog retains the existing three-tier layout.

**Validation for this chunk:** `make -C src -j4`,
`./scripts/format.sh --check`, `git diff --check`, and these direct tests passed:

```sh
python3 tests/async/test_named_set_catalog.py
python3 tests/async/test_random_equipment_golden.py
python3 tests/async/test_random_mob_theme_runtime.py
python3 tests/async/test_redis_module_boundaries.py
python3 tests/async/test_redis_admin_nonblocking.py
python3 tests/async/test_redis_failure_containment.py
SANITIZE=1 python3 tests/async/test_pager_contract.py
```

The new ASan/UBSan test freezes the original set and spawn data, checks catalog
counts and each invalid-definition case, and executes the real formatter and
command with cold/warm/expired/disabled cache boundary fixtures. Oversized zone
titles exceed the former total report buffer and still include every row.
These cache boundaries are fixtures, **not a live Redis lifecycle test**.
This chunk does not claim gameplay, persistence, or actual effect ownership
verification. The existing pager test remains the pager integration check.

### Persistent-origin chunk

`src/item/named_set_origin.c` now resolves positive virtual IDs from the reserved
`DURIS_NAMED_SET_ORIGIN_V1` extra description. An explicit marker wins even after
a visible-name change and even when its zone has no catalog row. Invalid or
duplicate markers return an invalid identity, never a guessed legacy origin.
Unmarked random blanks require the complete generated ` &+rfrom ` tag and an
exact color-normalized title, optionally followed by that weapon's registered
revealed-proc suffix. Ceothia, Underworld, and Braddistock legacy titles stay
ambiguous; the result carries their normalized title for the later HP-only
membership path. Reversing the zone table changes none of these results.

The generator stamps the selected room's virtual zone ID only for `ZONE_NAME`.
`identify_random()` records a uniquely resolved legacy origin before its name
mutation; cloning preserves the origin and refuses invalid source metadata.
Normal player extra-description lookup hides the marker. The two authored title
fixes are limited to #204 and #990. An isolated `make world` under
`bin/tests/named-set-world` verified their generated colored headers; generated
area files in the working checkout were not changed.

Snapshot capture, the shared item wire codec, player/pet SQL metadata loading,
SQL snapshot writers, direct saved-world/shop/corpse loaders, native legacy item
readers, and account reward snapshots validate the marker. Internal trap state
and origin each retain a separate slot outside the visible-description limit.
Length-aware stored-field parsing rejects embedded NULs; the native decoder
checks keywords before treating descriptions as text, preserving binary
spellbooks. The MySQL corpse path now propagates description-read failure and
refuses boot, retaining authoritative rows. The pfile extraction stub's pointer
signature was corrected because native-reader error cleanup now calls it.

**Ablation:** reuse ordinary extra descriptions, the current item codecs and load
failure policies. No schema, per-item field, bulk conversion, custom storage
service, or effect-specific adapter was added. Resolve legacy identities lazily
when consumed; wearing must still stamp unique legacy items before normal saves.

**Additional evidence:** the origin/runtime test and extended native restore
harness run under ASan/UBSan. They cover numeric origins for all seven problem
zones and counterparts, exact Tiamat titles, colored weapon suffixes, ambiguity,
name changes, cloning, hidden metadata, invalid metadata, nested wire storage,
native item files, saved-item SQL loader boundaries, and reward snapshots.
Player-item materialization tests reject malformed/conflicting origins before
allocation. The disposable MariaDB repository harness verifies player and pet
origins beside 64 visible descriptions plus trap metadata, conflicts, overflow,
and embedded NULs in both stored keyword and description. Flat-file repository
tests retain origin through cross-owner transfer/restart reconciliation and
corpse/saved-world catalogs. Exact equipment output and RNG sentinels still pass.

Relevant direct commands for the origin chunk:

```sh
python3 tests/async/test_named_set_origin.py
python3 tests/async/test_item_extra_descr_codec.py
python3 tests/async/test_player_item_snapshot_codec.py
python3 tests/async/test_player_snapshot_capture.py
python3 tests/async/test_player_load_items.py
python3 tests/async/test_legacy_trap_restore.py
python3 tests/async/test_artifact_creation_admission.py
python3 tests/async/test_item_transfer_codec.py
python3 tests/async/test_flatfile_item_repository.py
python3 tests/async/test_flatfile_world_item_repository.py
python3 tests/async/test_random_equipment_golden.py
python3 tests/async/test_account_reward_exact_contract.py
python3 tests/async/test_spellbook_persistence_contract.py
tests/async/run_player_load_repository_mysql.sh
make -C src -j4
make -C src -j4 PERSISTENCE_BACKEND=flatfile DMS_BINARY="$PWD/bin/tests/named-set-flatfile-server"
make -C src -j4 pfile
./scripts/format.sh --check
git diff --check
```

### Worn membership and HP cleanup chunk

The current branch routes `set_proc()`, `random_set()`, spell lookup and staff
object `stat` through the origin resolver. Unique legacy armor and weapons gain
their marker when worn; revealed names, renamed identified gear, and duplicate
blank prototypes still count correctly. Virtual IDs replace substring matches,
first-room arithmetic, and row-index contexts. Existing belt exclusions and
the HP formula are unchanged.

Ambiguous historical titles retain a separate HP-only group. Its context is the
negative smallest matching virtual zone ID, stable under zone-table reordering;
that value is a transient group key, **never an inferred origin or spell key**.
Identified items use positive IDs and cannot join a legacy group. Each group
refreshes its own cleanup event through the existing reschedule API. Event
payloads carry the context instead of an affect pointer, and expiration removes
only that group's HP. This also removes the callback's old freed-affect iteration.

**Ablation:** retain the current counting rules, HP affects, and event scheduler;
no extra membership registry, per-character reconciliation service, or timer
infrastructure was introduced. Ordinary-cast ownership, shared-spell support,
and cooldown repairs are the next independent chunk; this one does not claim
to solve them or install new effects.

`test_named_set_membership.py` executes the actual worn counting, tier selection,
HP update, and cleanup callers under ASan/UBSan. It covers 1/2/3/5/6/9 pieces,
Tharnadia's 3/5 thresholds, belts/back, random armor plus weapon blanks, mixed
duplicate-title origins, ambiguous legacy HP, lazy migration, renamed/revealed
weapons, Tiamat #196/#199, reversed zone order, two refresh deadlines and both
removal orders. Spell bodies and scheduler I/O are fixture boundaries here;
this is **not actual spell ownership or gameplay proof**. The real scheduler's
ASan/UBSan reschedule regression, origin test, and catalog/report test also pass.
Both maintained backend builds pass.

```sh
python3 tests/async/test_named_set_membership.py
python3 tests/async/test_named_set_origin.py
python3 tests/async/test_named_set_catalog.py
python3 tests/async/test_nevent_scheduler_runtime.py
make -C src -j4
make -C src -j4 PERSISTENCE_BACKEND=flatfile DMS_BINARY="$PWD/bin/tests/named-set-flatfile-server"
./scripts/format.sh --check
git diff --check
```

### Affect provenance and shared-support chunk

The current branch uses `named_set_grant` at invocation and the real
`affect_to_char()` allocation boundary. Only newly created affects receive
`set_zone`, `set_spell`, `set_owner`, and the existing SET/NOSAVE flags. These
three fields are transient provenance, not new stored item/character columns;
the persisted affect wire format is unchanged. Native context and link data are
preserved. The creator's existing process-local character runtime ID separates
a received group song from a set the recipient wears.

`reconcile_named_set_spell()` inspects current worn pieces, the armor driver,
and the existing belt exclusions. It retains one shared grant under another
qualifying zone without refreshing its duration, and removes only wearer-owned
nodes for the configured source spell. Ordinary nodes and other casters' linked
song markers survive. This replaces removal of every instance by native spell ID.
Configured-source metadata also handles effects whose native ID differs, such
as Vampire's Angelic Countenance branch.

The application entry now recognizes an existing native effect, a registered
callback alias, or its own source grant. This prevents set invocations from
refreshing ordinary alias durations and prevents repeated epic-stat grants.
Song of Dragons extends only newly created markers; its ordinary timed wards,
instant Invigorate consequences, and summons retain their native behavior.

**Ablation:** one creation scope and one shared-support pass replace bulk
retagging and bulk spell removal. No effect-specific adapter, ownership registry,
new persistence format, or timer layer was introduced. The creator ID is needed
by the existing group-song path; the configured spell ID is needed when native
affect IDs differ. One application-entry presence check replaces redundant
per-branch checks. Existing ordinary durations are left alone, with no extra
refresh when support changes zones.

`test_named_set_effect_ownership.py` runs actual Armor, Endurance, Strength,
multipart Vampiric Touch, Song of Dragons, affect allocation/removal, and song
link creation/removal under ASan/UBSan. Stat totals, output, scheduler I/O, and
unrelated handlers are boundaries. It proves ordinary-node preservation,
creation provenance, native-context preservation, shared support/removal in
both orders, armor/belt support checks, multipart cleanup, repeated epic grants,
and linked-song ownership. A callback boundary additionally verifies the real
Vampire/Angelic registration alias relationship. It **does not prove a successful
ordinary cast after a set grant**: native Armor currently refreshes that set
node in place, while native Endurance/Strength refuse the overlapping cast.

Both backend builds, the pfile tool, snapshot codec/capture checks, and the
existing Web Spray, poison lifecycle, Hatred, assassin, elemental-form and
freedom-of-movement regressions pass. Their extracted-function fixtures now
include the same owning header as production `affects.c`.

```sh
python3 tests/async/test_named_set_effect_ownership.py
python3 tests/async/test_named_set_membership.py
python3 tests/async/test_web_spray.py
python3 tests/async/test_freedom_of_movement_procs.py
python3 tests/async/test_assassin_mechanics_runtime.py
python3 tests/async/test_poison_lifecycle_runtime.py
python3 tests/async/test_innate_hatred.py
python3 tests/async/test_elemental_forms_runtime.py
python3 tests/async/test_player_item_snapshot_codec.py
python3 tests/async/test_player_snapshot_capture.py
python3 tests/async/test_pfile_tool.py
make -C src -j4
make -C src -j4 PERSISTENCE_BACKEND=flatfile DMS_BINARY="$PWD/bin/tests/named-set-flatfile-server"
./scripts/format.sh --check
git diff --check
```

**Next:** complete ordinary-cast entry handling in both orders and cooldown
ownership (section 5). Real ordinary casts after an existing set must gain their
own duration/source without stacking the set's numeric benefit. Re-equipping,
swapping the selected item, or alternating sets must not reset the three timed
families' cooldowns. Do not install expansion rows before these gates pass. Actual in-game
wear/transfer/save/reboot journeys, private chest/locker/shop journeys, live Redis
lifecycle checks, balance, help publication, and the wider eligibility review
remain outstanding. No production operation, release, or release tag has occurred.

For the next ownership change, direct native calls matter: group armor and
several item procedures call `spell_armor()` without the ordinary `sparser`
dispatch. Handling only that dispatcher would leave valid cast paths broken.
Match the source spell/registered alias, preserving other armor/light/shield
exclusions. The existing `AFFTYPE_NOAPPLY` path in `all_affects()` can suppress
a dormant source without changing numeric stacking rules; verify remaining
durations and reactivation on ordinary expiry/removal if that path is used.
The creation scope must continue to distinguish a set invocation from an
ordinary invocation. Test actual spell entries, not just ordinary affect-node
allocation, before checking off the both-orders acceptance gate.

### Historical Misty Vale identity correction

The history check above exposed a real collision hidden by the current world's
retired title. Both old #150 and pre-metadata #3000 items can carry the same
normalized `The Chasm of the Misty Vale` tag. They cannot be separated by current
zone availability or presentation colors. `named_set_origin()` now keeps that
unmarked title (including the registered revealed-weapon suffix) unresolved in
the HP-only legacy group with context **-150**. Explicit #150 and #3000 markers
remain authoritative. Newly marked #3000 pieces do not join the legacy group.

**Ablation:** one confirmed collision guard precedes the existing live-title
lookup. There is no new historical registry, runtime Git query, or migration.
The 104 assignments and their home counts remain unchanged, and #150 stays
excluded as inert metadata. Do not bulk rewrite unmarked items to either ID.

The ASan/UBSan origin and real worn-membership tests cover both explicit IDs,
old tags, revealed suffixes, zone reordering, an older world's loaded titles,
and separate +5 HP groups for three legacy versus three marked #3000 pieces.
The 1,480 generator cases and RNG sentinels still match their frozen fixtures.
This extends the identity proof; actual #3000 effect activation belongs to the
later installed-catalog/gameplay gate.

```sh
python3 tests/async/test_named_set_origin.py
python3 tests/async/test_named_set_membership.py
python3 tests/async/test_random_equipment_golden.py
make -C src -j4
make -C src -j4 PERSISTENCE_BACKEND=flatfile DMS_BINARY="$PWD/bin/tests/named-set-flatfile-server"
./scripts/format.sh --check
git diff --check
```

## Start here

1. Read this plan for implementation order, compatibility decisions, and proof.
2. Use the [effect inventory](named-zone-set-effect-inventory.md) for current
   effect counts, the retained 42 candidates, restrictions, and exclusions.
3. Use the [complete assignment plan](named-zone-set-first-pass-assignments.md)
   as the zone-to-effect mapping: 42 initial choices plus 62 reuse choices,
   covering all 104 zones in the issue's current missing-set roster. Its filename
   is retained even though it now includes both assignment passes.

The inventory's current counts describe source definitions. The assignment
document's proposed homes describe the intended expansion. Keep those two
counts distinct until the implementation lands.

## Outcome, boundaries, and proof

**Outcome:** eligible zones produce named gear whose persistent origin identifies
the correct set; wearing the required pieces grants the intended bonus and HP;
removing pieces cleans up only the appropriate benefits; both report paths show
the same complete roster. Resolve the seven named problem zones and finish the
issue's broader eligibility review before declaring #706 complete.

**Non-goals:** new high-impact effects, new effect-specific adapters, additional
bonus tiers for the 104 planned additions, changing named-drop probabilities,
changing ordinary item-affect/weapon-proc rolls, or changing roaming-NPC spawn
distribution. Existing sets retain their reviewed thresholds, effects, and
cooldown behavior. Required origin/persistence/ownership repairs are part of
this work, rather than reasons to bring excluded effect families back into scope.

**Files:** implement within the existing item, set-proc, persistence, report,
area, and focused-test owners listed below. A small shared named-set catalog
and origin resolver are justified by their generator, worn-gear, and report
callers. The creation scope and shared-support helper serve affect allocation
and set cleanup without a separate registry. Reuse the existing item persistence
and event mechanisms.

**Proof:** reconcile the source catalogs and assignments; exercise real set
application/removal; round-trip item identity through MySQL and flat-file
storage; compare cached and uncached reports; complete the specified local
gameplay journeys. CI is additional evidence, not a required wait or a substitute
for these checks.

## 1. Freeze the roster and first-pass balance decisions

- [ ] Recheck #706, the active [area registry](../../areas/AREA), and the two
  companion documents against the implementation checkout. Preserve all 104
  planned zone IDs, the original 42 choices, and the 62 reuse choices. The
  reuse pool has 50 effects: the 42 newly selected effects and eight existing
  simple effects. Every initially unused candidate has two or three proposed
  homes; 60 of the 62 reuse choices favored an effect with one home at that
  pass's start.
- [ ] Give each of the 104 additions one effect tier. Start the balance review
  with **three matching pieces** as the proposed threshold, giving the existing
  +5 maximum-HP bonus at that count. Record the final threshold for every row
  in the assignment document before installing the data.
- [ ] Check actual power at three pieces, five pieces, and six or more pieces.
  Most current spells use `min(56, pieces * 10)`; some handlers instead use the
  wearer's level, fixed values, class, or specialization. A higher piece
  requirement can also increase spell power. Validate the real functions and
  existing caps rather than assuming the candidate list proves numeric balance.
  If an assignment needs a special adapter or proves too powerful, revise that
  pairing using the retained simple pool and update its home counts explicitly.
- [ ] Preserve the Shaman restriction for Guardian Spirits (#780 and #422),
  Virtue's alignment condition, and light/darkness exclusions. Describe those
  restrictions in player-facing help/report notes so a set is not presented
  as granting a universal benefit when its spell is conditional.
- [ ] Complete the wider area review required by #706: classify remaining
  broad-screen candidates and excluded plain-title areas as independent set,
  explicitly shared set, or excluded with a reason. Check repeatable eligible
  kills and real player access, including secret/locked paths and gated planes.
  The 104-zone roster is a confirmed work queue, not the final world denominator.
  Add further eligible areas to the same assignment document using the simple
  effect pool; reconcile the totals again.

The roster exclusions #380, #384, #536, #870, and #1422 remain recorded unless
new evidence and a content decision change them. Review the four existing
plain-title set zones (#87, #370, #676, #824) separately: either restore naming
eligibility for a verified playable area or record why it remains legacy-only.
Also classify the duplicate-name counterparts #1350 and #300; resolving their
identity does not automatically give them the new #13 or #44 bonus.

## 2. Separate set definitions from roaming spawn data

Owning code: [random.mob.c](../../src/world/random.mob.c),
[specs.object.c](../../src/specs/specs.object.c),
[redis_report_cache.c](../../src/redis/redis_report_cache.c), and
[testcmd.c](../../src/cmd/testcmd.c).

- [x] Introduce one canonical set catalog keyed by the virtual zone number.
  Move the existing resolved spell definitions into it, preserving their
  values. Route worn-set lookup, both reports, and staff set diagnostics through
  that catalog; remove duplicate spell-data definitions and declarations.
- [x] Preserve the existing roaming selector's zone/race rows, order, sampling,
  abort behavior, and random-number consumption. `create_random_mob()` must not
  sample newly added set rows. Do not silently remove stale spawn rows while
  separating these responsibilities.
- [x] Keep unresolved set IDs #30 and #250 outside the active set catalog,
  documented as stale rather than automatically reassigned to #28 or #254.
- [x] Use the catalog's actual extent. The old 200-slot table and the staff
  dump's 100-row cutoff cannot serve the expansion. Validate duplicate IDs,
  missing zones, positive/reachable thresholds, effect IDs, and supported
  handlers. Ordinary skills and songs without explicit support must not reach
  the generic null spell-pointer call.

For the currently planned cohort, the expected active catalog is **219 loaded
zone rows** (115 existing + 104 additions), **310 zone/effect assignments**
(206 + 104), and **106 distinct effect IDs** (64 existing + 42 newly used).
These are baseline reconciliation targets; update them when the wider roster
review changes the final scope. Each valid old row must survive this extraction.

## 3. Give named items a durable, unambiguous origin

Owning code: [random_equipment.c](../../src/item/random_equipment.c),
[structs.h](../../src/core/structs.h),
[item_extra_descr_codec.h](../../src/sql/item_extra_descr_codec.h),
[player_snapshot_capture.c](../../src/player/player_snapshot_capture.c),
[player_snapshot_codec.c](../../src/player/player_snapshot_codec.c),
[player_snapshot_repository.c](../../src/player/player_snapshot_repository.c),
[player_load_items.c](../../src/player/player_load_items.c),
[sql_player.c](../../src/sql/sql_player.c), and the legacy item serialization in
[files.c](../../src/core/files.c).

- [x] Use a reserved internal item extra-description marker, proposed as
  `DURIS_NAMED_SET_ORIGIN_V1`, with a strictly parsed positive virtual zone ID.
  Reuse the existing canonical item extra-description storage pattern already
  used for internal trap state. Keep it out of normal player look/edit output,
  preserve it when visible names change, and validate duplicate or conflicting
  markers. This avoids a new per-item SQL column or a second metadata service.
- [x] Set the marker only after the generator chooses `ZONE_NAME`, using
  `zone_table[world[finder->in_room].zone].number`. Store the origin even if that
  zone currently has no spell row: HP membership and future set definitions
  still need it. Owner-named and plain items do not become zone-set items.
- [x] Share one resolver between the generator's identity helpers, worn-piece
  counting, spell lookup, and diagnostics. Use the explicit ID, not zone-table
  indices, first-room arithmetic, display color, or substring matches. Keep
  `identify_random()` / `reveal true name` suffix changes independent of origin.
- [ ] Prove that the marker survives complete and incremental saves, nested
  containers, transfer between characters, player/pet/corpse/locker/chest/shop
  and saved-world item paths, reboot, and both database backends. Include copy,
  clone, and staff item-edit paths that can touch descriptions. An older reader
  that preserves ordinary extra descriptions must retain the marker for a later
  upgraded reader.
- [ ] Validate the complete stored marker before materialization. An absent
  marker takes the legacy path below; malformed or conflicting metadata must
  never silently fall back to guessing a zone from the name. Surface an
  actionable staff diagnostic and use the established item-load failure policy;
  never silently discard the item or corrupt the rest of its ownership graph.

Do not place the ID in `obj_affect.extra2`: `set_obj_affected_extra()` ORs that
value into item flags, and the SQL item writer does not preserve arbitrary
dynamic-affect payloads the way the flat-file snapshot does. This is why the
existing extra-description path is the selected reuse point. Extend its
validation and round-trip tests; keep trap and spellbook metadata independent.

### Legacy item policy

- [x] For an unmarked item, parse the actual named-equipment tag and match a
  complete historical zone title. Permit only recognized generated suffixes,
  including the weapon spell suffix, rather than arbitrary trailing text.
  Normalize presentation colors for matching and require a unique zone result.
  Resolve existing unique-origin items to IDs and persist that result through
  normal saves; do not run a bulk player-data rewrite.
- [x] Treat historical duplicate titles as unresolved when their origin cannot
  be proved. Keep their legacy matching-tag HP group and the HP formula, but
  grant no newly selected zone spell on a guessed origin. Do not merge such a
  legacy group with an identified new set. Document this limitation; staff may
  correct an origin through existing item tools only with reliable provenance.
- [x] Do not infer the old origin from the current room, carrier, numeric object
  blank, or the first matching zone. Do not randomly divide indistinguishable
  Ceothia, Underworld, or Braddistock items among the new IDs.
- [x] Test exact and prefix titles beyond the seven rows too, especially Tiamat
  #196 versus Astral Plane, Tiamat #199. Correct the erroneous substring lookup
  rather than preserving a wrong-zone grant as compatibility behavior.

## 4. Fix the seven roster zones

The five duplicate-title zones use the shared ID repair above. Their authored
titles can remain intact; reports and staff diagnostics must include the
virtual zone ID so the records are distinguishable. The two plain-title zones
receive narrowly scoped color changes in their authored `.zon` files, preserving
their visible wording and the generator's existing eligibility rule elsewhere.

| Zone | Assigned effect | Required work | Proof |
|---|---|---|---|
| #13 Braddistock Mansion | Phantom Armor (#400) | Tag new drops as #13. Keep `braddistock.zon` distinct from `brad.zon` #1350. Apply the ambiguous-legacy policy to their identical old title. | New #13 and #1350 items never count together; #13 grants only its own row. Reversing zone order has no effect. |
| #44 The Underworld | Globe of Darkness (#302) | Tag new drops as #44. Keep `underworld.zon` distinct from `underworld3.zon` #300. Preserve light/darkness exclusions. | New #44 and #300 items remain separate after transfer and reload; unresolved old tags gain no guessed new spell. |
| #808 Ceothia, present | Enhance Agility (#177) | Tag `ceothia.zon` drops as #808. Show the ID in reports and preserve independent era membership. | #808 pieces grant Enhance Agility and do not contribute to #811 or #814. |
| #811 Ceothia, past | Protection from Animals (#383) | Tag `ceopast.zon` drops as #811. Ignore the extra leading color reset as an identity mechanism. | #811 pieces grant Protection from Animals; all three era permutations and legacy tags are checked. |
| #814 Ceothia, future | Vapor Strike (#467) | Tag `ceofutur.zon` drops as #814. Keep its set separate from present/past Ceothia. | #814 pieces grant Vapor Strike; a mixed three-era outfit cannot manufacture a matching set. |
| #204 Neverwind Valley | Sense Life (#44) | Wrap the existing title in `pyramid.zon` with normal MUD color/reset codes, preserving the visible name. Regenerate the world and stamp new drops with #204. | A forced successful eligible naming roll now yields a named #204 item; a failed roll still follows existing behavior. Wear/reload/report agree. |
| #990 Neverwinter Woods | Scent of the Bloodhound (#517) | Apply the same narrow title fix in `moria.zon`, then regenerate the world and stamp new drops with #990. | Named #990 generation, set activation, removal, and reload work; no other plain-title zone is enabled as a side effect. |

Source files: [braddistock.zon](../../areas/zon/braddistock.zon),
[brad.zon](../../areas/zon/brad.zon), [underworld.zon](../../areas/zon/underworld.zon),
[underworld3.zon](../../areas/zon/underworld3.zon),
[ceothia.zon](../../areas/zon/ceothia.zon), [ceopast.zon](../../areas/zon/ceopast.zon),
[ceofutur.zon](../../areas/zon/ceofutur.zon), [pyramid.zon](../../areas/zon/pyramid.zon),
and [moria.zon](../../areas/zon/moria.zon).

## 5. Make membership, ownership, and cleanup agree

Owning code: `set_proc()`, `random_set()`, `check_zone_spells()`, and
`apply_zone_spell()` in [specs.object.c](../../src/specs/specs.object.c),
[affects.c](../../src/magic/affects.c), and [new_events.c](../../src/world/new_events.c).

- [x] Count eligible worn random armor/weapon blanks by resolved origin ID.
  Retain the current belt-slot rules, worn-armor-driven periodic processing,
  and `5 * (count - 2)` HP formula. Preserve ordinary gear HP cap behavior.
- [x] Replace row-index contexts with unambiguous nonzero source identity.
  Index zero must not become a wildcard. Cancel or reconcile cleanup for the
  relevant set; one set's refresh must not cancel another set's wear-off.
- [x] Mark only affects actually created for a set invocation. Never adopt an
  existing ordinary cast by marking every affect of the same spell type.
  Remove only matching set-owned affects, not every instance of that spell ID.
- [ ] Before removing a shared spell, reconcile all currently qualifying worn
  sets. The spell must remain supported while another set still qualifies,
  without stacking duplicate buffs merely because two zones use it. Verify
  ordinary casts both before and after the set grant; preserve their independent
  durations and source ownership. Keep any ownership helper limited to these
  demonstrated set/cast collisions.
- [ ] Preserve existing timed effects and their reapplication constraints.
  Re-equipping, swapping the selected item, or alternating two sets must not
  create unintended fresh grants or bypass cooldowns. Trace linked/group
  effects already present in old sets while retaining the new simple-effect scope.

## 6. Install the catalog and publish one consistent report

- [ ] Add the 104 assigned rows only after ID membership and cleanup pass their
  focused regressions. Use the assignment document as the mapping authority,
  including independent Barovia/Barovia Continued IDs that intentionally reuse
  Lifelust. Add any further zones accepted by the wider review with recorded
  mappings and updated counts.
- [ ] Make Redis-cached and uncached `namedreport` use the same catalog and
  formatting path. Include zone IDs, piece requirements, conditional-effect
  notes, and existing cooldown markers. Replace fixed-size concatenation with
  bounded/growing output so the expanded roster is complete and paginates safely.
- [ ] Update the staff diagnostic to traverse the complete real catalog and
  use registered effect names. Keep roaming-spawn diagnostics separate.
- [ ] Verify cold cache, warm cache, Redis unavailable/disabled, boot warming,
  expiry, and staff invalidation. The existing one-day cache must not keep an
  old roster after rollout; invalidate the named-report cache explicitly.
- [ ] Update the canonical Named Equipment Sets help and its active MySQL and
  flat-file publication paths. Explain thresholds/HP, numeric origin identity,
  conditional effects, and ambiguous legacy items. Use
  [help_index](../../lib/information/help_index) and the existing help catalog
  tooling, rather than introducing another content source.

## 7. Verification gates

Extend existing harnesses where they already exercise the owning code. Add
focused named-set runtime/report fixtures where coverage is missing; a parsed
table or a stubbed spell recorder alone cannot prove actual affect ownership.

| Gate | Required cases and evidence |
|---|---|
| Catalog and roster | Preserve all 115 resolved old rows; account for the two stale IDs; install all 104 planned IDs; verify the 219/310/106 baseline counts and adjust for explicit wider-review changes. Detect missing/duplicate zones, unsupported effects, and invalid thresholds. |
| Seven zones and identity | Exercise all seven fixes, counterpart #1350/#300, all Ceothia pairs, Tiamat #196/#199, color changes, revealed weapon names, unique legacy tags, ambiguous tags, invalid metadata, and zone-order changes. |
| Membership and HP | Test 1/2/3/5/6+ pieces, mixed origins, armor plus weapons, the two excluded belt attachments, back/allowed belt positions, duplicate blanks, and removal. Tharnadia specifically gives +0 HP at 2, Armor/+5 HP at 3, Armor/Endurance/+15 HP at 5. |
| Actual effects and cleanup | Exercise every selected handler at representative and maximum effective power, including Shaman/non-Shaman Guardian Spirits, opposed/neutral alignment, and light/darkness conflicts. Test two sets with different spells, two sharing one spell, ordinary casts in both orders, removing either set first, expiry, dispel, re-equipping, and old cooldown/summon behavior. |
| Persistence and transfer | Verify exact origin round-trips on MySQL and flat-file backends, legacy item files, player/pet inventories, nested bags, corpses, private chests/lockers, shops, and saved-world objects. Include actual transfer, save completion, disconnect/reboot/reload, and metadata surviving visible-name edits. |
| Reports | Compare full semantic output with and without Redis, all rows past the old 100-row cutoff, stable ordering, IDs on duplicate titles, pagination, buffer boundaries, invalidation, and boot warming. |
| Gameplay | Use a local/dev test account and controlled drops for Bloodstone Keep plus another newly covered zone, then the seven repaired zones. Verify inventory/report/worn effects and save/reload. Do not depend on random farming to establish deterministic correctness. |
| Regression | Keep generator output/RNG sentinels and roaming-mob selection behavior green. A new origin marker should not change the old naming rolls, stats, proc outcomes, or roaming selection distribution. |

Existing focused commands to retain in the implementation workflow:

```sh
python3 tests/async/test_random_equipment_golden.py
python3 tests/async/test_random_equipment_config_contract.py
python3 tests/async/test_random_equipment_config_runtime.py
python3 tests/async/test_random_mob_theme_runtime.py
python3 tests/async/test_item_extra_descr_codec.py
python3 tests/async/test_player_item_snapshot_codec.py
python3 tests/async/test_item_transfer_codec.py
python3 tests/async/test_flatfile_item_repository.py
python3 tests/async/test_flatfile_world_item_repository.py
```

Run the new focused named-set tests directly as they are added. For C/C++ changes,
run `./scripts/format.sh --check` and `make -C src`. Regenerate authored area
changes with `make world` in the isolated test checkout, and verify the intended
zone headers. Keep artifacts under `bin/` and generated area outputs uncommitted.
Run affected MySQL persistence journeys against an isolated local/test database;
inspect each test's configuration before invoking it. Report unavailable checks
instead of claiming source inspection is a completed gameplay journey.

## 8. Rollout and issue completion

- [ ] Finish the reviewed eligibility roster with independent/shared/excluded
  decisions and exact counts. Record any unresolved area as outstanding work;
  the full issue cannot close solely because the initial 104 rows are assigned.
- [ ] Complete local builds, focused tests, both-backend journeys, and review.
  Prepare release/help notes from the resulting behavior and the legacy policy.
- [ ] For production, use the owner's deployment permission and the existing
  deployment workflow. Publish authored world/help changes, restart into the
  verified build, refresh the report cache, and smoke-test named drops and
  effects. Any persistence/schema change discovered during implementation must
  be additive, guarded, and tested before a production operation.
- [ ] Keep a rollback revision and compatible persisted metadata. Rehearse a
  rollback that retains the origin marker, removes transient set-owned character
  effects on reload, and refreshes reports; do not erase player items or guessed
  origins to recover. If an older build cannot safely interpret the new naming
  state, use a compatibility rollback build rather than silently losing identity.
- [ ] Attach the final roster, implementation references, local validation
  results, gameplay evidence, and deployment status to #706 through the agreed
  issue workflow. Close it only when all acceptance criteria and the final
  eligibility review are satisfied.

## Suggested commit sequence on this branch

1. Planning documents and cross-references (this commit).
2. Canonical set catalog, spawn separation, and baseline/report diagnostics tests.
3. Persistent origin, legacy resolution, seven-zone repairs, and identity journeys.
4. Membership/ownership/cleanup repairs with mixed-set and ordinary-cast tests.
5. Validated thresholds, the 104 assignments plus any reviewed additions, report
   publication, help, and final both-backend gameplay evidence.

Keep each implementation commit reviewable and locally verified. The companion
documents remain the recorded effect and assignment decisions; update them when
implementation evidence changes a choice or count.
