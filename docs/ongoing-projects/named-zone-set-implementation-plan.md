# Named zone sets: end-to-end implementation plan

Status: implementation in progress; nineteen focused implementation/test PRs are pushed
and ready for review, including the expanded catalog #732 after native gameplay validation.
Date: 2026-11-06.
Issue: [#706 — Extend named random equipment set bonuses to all eligible zones](https://github.com/LuminariMUD/Duris/issues/706).
Working branch: `branch/named-zone-set-mariadb-chest`, based on
`branch/named-zone-set-locker-storage`.
Initial inspected source baseline: `2d2a7d48dea91dbe773701790239db76f59806c2`.

## Current handoff (2026-11-06)

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
[PR #727](https://github.com/LuminariMUD/Duris/pull/727)
(`branch/named-zone-set-ordinary-casts`, implementation commit `a7d720db5`)
contains ordinary-cast overlap handling and targets the historical-origin branch.
[PR #728](https://github.com/LuminariMUD/Duris/pull/728)
(`branch/named-zone-set-cooldowns`, implementation commit `bf2b4ce9e`)
contains persistent wearer cooldowns and targets the ordinary-cast branch.
[PR #729](https://github.com/LuminariMUD/Duris/pull/729)
(`branch/named-zone-set-effect-qualification`, implementation commit `41f777a93`)
contains native effect qualification and the 104 recorded piece requirements;
it targets the cooldown branch.
[PR #730](https://github.com/LuminariMUD/Duris/pull/730)
(`branch/named-zone-set-eligibility`, implementation commit `a54b99654`)
restores authored naming eligibility for four existing sets and targets the
qualification branch. The wider eligibility review is complete in the catalog
checkpoint below.
All nine PRs are ready for review; no implementation PR has been merged and no
release has been performed.
[PR #732](https://github.com/LuminariMUD/Duris/pull/732)
(`branch/named-zone-set-roster`, implementation commit `0ad13149a`)
adds the complete reviewed catalog and targets #730. Its native catalog gameplay
gate now passes as recorded below; it is ready for review.
[PR #733](https://github.com/LuminariMUD/Duris/pull/733)
(`branch/named-zone-set-native-journey`, implementation commits `4ebf192f8` / `f438741b9`)
adds the native Tharnadia 2/3/4/5-piece wear, ordinary Armor and reboot journey and
targets #732. This focused test chunk is ready for review.
[PR #734](https://github.com/LuminariMUD/Duris/pull/734)
(`branch/named-zone-set-area-journeys`, implementation commit `0afe7cba2`)
extends the native runner to the required areas and targets #733. All twelve
native area/identity cases pass as recorded below. This focused runner/area-proof
chunk is ready for review.
[PR #735](https://github.com/LuminariMUD/Duris/pull/735)
(`branch/named-zone-set-title-journeys`, implementation commit `397381d89`)
completes the four existing-title native journeys, including six-piece Vitality,
and targets #734. It is ready for review.
[PR #736](https://github.com/LuminariMUD/Duris/pull/736)
(`branch/named-zone-set-transfer`, implementation commit `ffece9482`)
adds native cross-owner nested transfer and effective ordinary Armor proof and
targets #735. It is ready for review.
[PR #737](https://github.com/LuminariMUD/Duris/pull/737)
(`branch/named-zone-set-edits`, implementation commit `ff7cfb214`)
proves native visible-name edits, recursive cloning and copied/mixed outfit
reload behavior; it targets #736 and is ready for review.
[PR #738](https://github.com/LuminariMUD/Duris/pull/738)
(`branch/named-zone-set-pet-storage`, implementation commit `318668bfd`)
proves native pet-held nested items and recovery and fixes fixture bookkeeping
retention; it targets #737 and is ready for review.
[PR #739](https://github.com/LuminariMUD/Duris/pull/739)
(`branch/named-zone-set-corpse-storage`, implementation commit `8f1e22722`)
proves native player-corpse persistence, boot/loot and exact graph recovery;
it targets #738 and is ready for review.
[PR #740](https://github.com/LuminariMUD/Duris/pull/740)
(`branch/named-zone-set-locker-storage`, implementation commit `8215b66c4`)
proves funded native public-locker custody and retrieval, with the failed
unfunded setup loss disclosed; it targets #739 and is ready for review.
[PR #741](https://github.com/LuminariMUD/Duris/pull/741)
(`branch/named-zone-set-mariadb-chest`, implementation commit `ce8594083`)
proves native MariaDB player and private-chest persistence, retrieval and worn
set recovery; it targets #740 and is ready for review.

The stack includes upstream `master` through `d4b3469c0` (#711 and #721), merged
into the foundation and propagated through each dependent branch without
rewriting history. PR #721 adds inert #150 metadata for retired Misty Chasm
prototypes, with no rooms or resets; it does not add a playable set candidate.
The playable Misty Vale remains #3000 in the 104-zone assignment roster. The
final reviewed roster uses this current area registry; keep the initial
inventory counts distinct from the final reviewed denominator.
History check: `c79fde573^:areas/zon/mist_chasm.zon` gives retired #150 the
same normalized title as new #3000. The historical-origin correction after #722
keeps unmarked Misty Vale gear from inheriting #3000's newly assigned effect by
guessing; see the checkpoint below.

The first implementation chunk extracted the **115 existing loaded set rows,
206 tiers, and 64 effect IDs** into `src/item/named_sets.c`. The current test build
adds the reviewed 183 rows (see the catalog chunk below). All **117 historical roaming rows**, their ordering and
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

**Subsequent work:** the ordinary-cast and cooldown chunks below implement these
entry/ownership requirements (section 5). Do not install expansion rows before
their required gameplay gates pass. Actual in-game
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

### Ordinary cast overlap

The current branch adds one `named_set_ordinary_cast` scope to the actual buff
entries, covering direct item/group calls as well as `sparser`: **103 entries**
from the existing and assigned effect pool. There are 104 registered spell
callbacks plus Song of Dragons; instant Invigorate and Conjure Elemental have
no owned buff nodes and need no entry scope, while the epic-stat skill has no
ordinary spell callback. Each entry uses its actual affect recipient (92 use
`victim`, ten use `ch`, and the song uses both), preserving unaffected caster
stats and native exclusions. No effect's numeric formula was changed.

During an ordinary native call the overlapping set nodes are temporarily
detached, retaining their links and remaining duration. When the cast returns,
the original nodes are restored; the existing `AFFTYPE_NOAPPLY` mechanism plus
`AFFTYPE_SET_SUSPENDED` makes the set copy dormant while an ordinary equivalent
applies. Both clocks continue to tick. Ordinary expiry or single-counter
exhaustion resumes only the original surviving node, never a fresh set grant.
Normal set cleanup still controls wearing eligibility and its existing grace
period; removing the set first preserves the ordinary node.

Explicit whole-spell removal (`affect_from_char`, including dispel/reveal)
retains its native behavior of clearing that type across sources. Dispel
selection snapshots active types before removal, so list order and resumed
nodes do not change its targets. Generic active-affect queries and score/GMCP
output skip suspended nodes. The skin and sphere consumers use the active
counter rather than spending or bulk-removing a dormant copy. `affect_join`
does not merge an ordinary node into an owned set grant or adopt an ordinary
node during a set invocation.

**Ablation:** reuse native nodes, the normal duration/update path, and NOAPPLY;
no shadow registry, persisted suspension format, extra timer, or effect adapter.
The scope has exactly two possible recipients, with no outer heap allocation.
Its one-recipient form covers the usual entries; only the existing song path
needs both. Source invocations bypass the ordinary guard. Existing native
fixtures use empty weak boundaries when named equipment is outside their
scope; the named-set regression links the real implementation.

The extended ASan/UBSan ownership test passes actual Armor/Endurance entries,
independent real affect ticks, recasting, set-first and ordinary-first removal,
native refusal, Miracle's direct Armor call, active dispel traversal, Stoneskin
and sphere counters, and received-song links. Stat totals, saving boundaries,
unrelated Miracle components, and general world/output behavior remain fixtures.
Full command/persistence gameplay and all-handler conditional/power gates remain
outstanding; cooldown ownership is the next separate chunk.

Both maintained backend builds and pfile checks pass. The prior Web Spray,
freedom-of-movement, assassin, poison, Hatred, elemental-form, snapshot and capture
regressions also pass on this branch. Additional checks cover the real scheduler,
shoreline affect removal, and conjurer fire behavior. Direct commands include:

```sh
python3 tests/async/test_named_set_effect_ownership.py
python3 tests/async/test_named_set_membership.py
python3 tests/async/test_conjurer_fire_runtime.py
python3 tests/async/test_water_shoreline_runtime.py
python3 tests/async/test_nevent_scheduler_runtime.py
make -C src -j4
make -C src -j4 PERSISTENCE_BACKEND=flatfile DMS_BINARY="$PWD/bin/tests/named-set-flatfile-server"
./scripts/format.sh --check
git diff --check
```

Cooldown investigation: existing persisted short affects already capture the
remaining event pulses in `player_snapshot_capture.c`; `enter_game()` in
`account/nanny.c` advances SHORT+OFFLINE events by elapsed offline pulses.
`affect_timer()` uses `TAG_SKILL_TIMER` but deliberately bypasses trusted staff,
so the implementation below creates timers directly. The spell-ID namespace and
pet/NPC restore paths were checked before selecting that reuse. Explicit timer
exclusion from grant provenance prevents SET/NOSAVE ownership and gear cleanup.

The branch also includes parent review fixes through `db3967686`: shared level
caps, legacy HP membership for retired/unloaded titles, no origin stamping on
unworn pieces, and regranting Song of Dragons to group members who lost theirs.
The merge is history-preserving. Ownership, membership, and the added
`test_named_set_effect_levels.py` pass after integration, as do both backend
builds. Preserve those fixes when implementing the cooldown chunk.

### Cooldown chunk

**Outcome:** Stoneskin, Invigorate and Conjure Elemental share one cooldown per
wearer and configured spell across driver replacements, re-equipping, alternating
zone sets, and save/reload. The original object's `timer[0]` check remains a
transfer floor. Existing property names/defaults (60/60/300 seconds), cast level
caps, full-vitality/skin preconditions and native invocation consequences remain.
An attempted native invocation consumes the cooldown as before, even if the
native handler refuses a summon. Ordinary spell entry points ignore these timers.

**Non-goals:** no new SQL columns, timer service, configuration or change to
ordinary spell cooldowns. No expansion assignments are installed in this chunk.

**Files/ablation:** `named_set_effects.{h,c}` reuses `TAG_SKILL_TIMER` and the
existing short-affect scheduler. The three spell IDs have no existing skill-timer
producer/consumer collision. Direct timer creation avoids `affect_timer()`'s staff
bypass. Timers are STORE+SHORT+OFFLINE and are explicitly excluded by grant
provenance; unlike set buffs, they are saved and survive equipment cleanup.
The three cases in `specs.object.c` check the wearer timer before invoking and
start it after invocation. This avoids a second timing mechanism or per-zone
timer state. Generic data-only timer exclusion is narrower than restructuring
every spell invocation's grant scope.

PC snapshots already save the remaining short-event pulses and restore them
through `affect_to_char()`; login advances OFFLINE events by elapsed offline time.
The real reboot test exposed a later blanket `TAG_SKILL_TIMER` reset in login.
`account/nanny.c` now resets only non-OFFLINE skill timers, preserving the ordinary
notch timers' reset behavior and the named timers' already-adjusted countdowns.
Pets did not save arbitrary affects, so `pet_restore_state` now supports a v2
extension containing three absolute deadlines. `pet_restore_runtime.c` writes v2
only while a cooldown exists and restores only unexpired time. Pet deadlines round
up to whole seconds, never shortening the saved cooldown. V1 remains readable and
is still emitted for summoned pets without active cooldowns. Ordinary pets without
cooldowns still have no payload. Ordinary v2 pets restore only timers;
`player_load_pets.c` retains their existing prototype, saved maxima and charm path.
Summoned pets retain their full existing stat/identity/lifetime path. Older readers
hold unknown v2 pet payloads and their equipment for review rather than guessing;
rollback must account for this existing recovery behavior.

**Focused proof passed:** `test_named_set_cooldowns.py` uses the real grant dispatcher,
affect allocation/removal, scheduler, snapshot wire, player affect restore loop,
offline-login and final timer-reset loops, and pet capture/apply. Native spell
consequences, output and stat totals are fixtures. It covers driver/zone swaps,
transfer floors, independent wearers, trusted staff, equipment cleanup, actual expiry, player reload/offline
expiry, ordinary casts and both ordinary/summoned pet deadlines. The existing
pet-state codec test covers v1/v2 and malformed deadlines; the loader test adds
ordinary v2 pet resource/charm compatibility. Full interpreter-driven grants and
gear swaps, live SQL cooldown storage, and an ordinary-pet reboot journey remain
required before project completion.
Both MariaDB and flat-file builds, the cooldown/ownership/level tests, pet-state
codec, player item/pet loader, snapshot capture, and Conjurer fire runtime pass.
The extended isolated flat-file server journey preserves player short timers and
summoned-pet v2 deadlines through two reconnect/save/reboot cycles. Existing pet
identity/stats/equipment, offline artifact expiry, finite-pet death and held-item
recovery also pass. The new cooldown state in this journey is seeded offline;
native grant/gear-swap guards are exercised by the separate scheduler regression.

```sh
python3 tests/async/test_named_set_cooldowns.py
python3 tests/async/test_named_set_effect_ownership.py
python3 tests/async/test_named_set_effect_levels.py
python3 tests/async/test_pet_restore_state.py
python3 tests/async/test_player_load_items.py
python3 tests/async/test_player_snapshot_capture.py
python3 tests/async/test_conjurer_fire_runtime.py
python3 tests/async/test_pet_restart_journey.py "$PWD/bin/tests/named-set-flatfile-server"
make -C src -j4
make -C src -j4 PERSISTENCE_BACKEND=flatfile DMS_BINARY="$PWD/bin/tests/named-set-flatfile-server"
./scripts/format.sh --check
git diff --check
```

**Next:** audit every selected handler's actual power at 3/5/6 pieces and at its
maximum effective level, including conditional class/alignment/light cases;
record final piece requirements in the assignment document. Complete the wider
world eligibility review before installing the expansion rows. The remaining
end-to-end origin/gear/storage journeys, live Redis lifecycle, help/publication
and compatibility rollback gates remain open below.

Publication note (2026-11-06): native SSH/HTTPS pushes failed with GitHub's internal
`commit_refs_rules` error, with no applicable branch rules. The Git data API
published the exact local blobs, tree and commit after SHA verification and moved
the branch forward without rewriting history. Local and remote revisions match.
Subsequent native pushes succeeded; ordinary Git publishing is working again.

### Effect qualification and piece requirements

**Outcome:** preserve the 104 planned pairings and 50-effect reuse pool, record
every final threshold, and qualify actual native grants before installing data.
The [assignment document](named-zone-set-first-pass-assignments.md#balance-qualification-and-final-piece-requirements)
now records **98 three-piece, four five-piece and two six-piece assignments**.
Adrenaline Control and Battletide require five pieces at both new homes; Guardian
Spirits requires six at #422/#780. Those fixed, larger grants justify the higher
requirements. The other assignments remain at the proposed three pieces. No
home count or zone/effect pairing changed and no expansion row is installed yet.

**Files/ablation:** extend `test_named_set_effect_ownership.py` instead of adding
another harness, and keep the thresholds with the existing assignment owner.
Native spell formulas, class rules, effect durations and flags are unchanged.
The Guardian Spirits source comment and companion inventory now correctly say
any Shaman specialization. Virtue's recorded rule is corrected to good against
non-good and evil against non-evil, including neutral targets; neutral wearers
receive no accuracy bonus. This is a documentation correction to the existing
combat branch, not a new combat rule. No adapters or balance configuration added.

**Proof:** the expanded ASan/UBSan executable qualifies all 50 handlers at
3/5/6/12/40 pieces, wearer levels 12/56, non-Shaman/Shaman/Animalist classes and
both RNG endpoints. IDs and callbacks must match the actual registrations and
the assignment pool. Frozen expectations check modifier/duration/bitvector and
provenance fields, ordinary casts in both orders, no periodic refresh, cleanup,
expiry and native dispel flags. Additional cases execute Virtue's real combat
branch across all good/neutral/evil boundaries, light conflicts in both orders,
armor/vision/Shaman-movement exclusions and shared detection bits. Recalculation
calls are checked for successful light creation/removal. Derived character stat
totals, actual room-light totals and interpreter/world behavior remain fixture
boundaries and require the full gameplay gates below. Do not treat this native
qualification as proof of those journeys.

Run `python3 tests/async/test_named_set_effect_ownership.py` for this qualification.
Both backend builds, the unchanged-catalog regression, worn membership regression,
format and diff checks also pass. The issue body was rechecked on 2026-11-06;
its `updated_at` remains `2026-11-05T08:15:32Z`. All 104 issue IDs and the original
zone/effect pairings match the assignment document exactly; its piece-count
distribution was independently recounted.
The parent harness fixes through historical-origin head `389e6d331` were merged
without rewriting history into ordinary casts (`8ae7887cc`), cooldowns
(`f7de76f10`) and this qualification branch (`57697bb5b`). They add origin
declarations to the GMCP harness and link the real resolver into the quest target
audit; neither changes production behavior. Both
`python3 tests/async/test_gui_gmcp_contract.py` and
`python3 tests/async/test_world_quest_target_retries.py` pass after integration.
The next independent chunk is the wider area eligibility review, followed by
catalog installation with the recorded thresholds and end-to-end gameplay,
storage, report/cache, help/publication and rollback checks.

### Wider eligibility review

**Outcome:** classify the active world beyond the original 104 assignments,
including plain-title areas, independently keyed duplicate-title counterparts,
connectors/infrastructure and gated or disconnected destinations. Preserve the
owner's exclusions. Record eligible additions and simple-pool assignments with
their access and encounter evidence before installing the final catalog.

**Non-goals/files/ablation:** use the existing assignment/plan documents and
authored area/route owners. Do not restore disabled entrances or change spawn/drop
rules to manufacture eligibility. A fresh isolated `make world` from `8d01225ef`
under `bin/tests/named-set-roster-world` contains **354 records, 253,452 rooms and
17,826 mobile prototypes**. The extra record versus the issue's 353-record baseline
is inert retired #150. The 115 existing and 104 planned IDs leave 135 records to
classify, including Limbo/Heaven/end/maps. Generated files in the working checkout
are untouched.

Important evidence: authored XP is not an eligibility filter. `read_mobile()`
calls `convertMob()`, which normally assigns positive XP even when the `.mob` XP
field is zero; ACT_IGNORE/`_ignore_` exceptions retain their authored XP. Apply the
actual shopkeeper, guild-room and recognized-hometown level guards. The temporary
audit must distinguish ZONE_SAFE from ROOM_SAFE: some commands/reward systems
check ZONE_SAFE, but ordinary kill/attack admission goes through CanDoFightMove
and checks ROOM_SAFE. Do not exclude Forgotten Forest #827 merely for ZONE_SAFE;
Wandering Fields #366 is population staging rather than a destination.
The temporary
audit records reset encounters, cross-zone exits and placed ITEM_TELEPORT routes;
its topology search includes closed/locked/secret doors but excludes closed/private
zones, guild rooms and map mountain barriers. Its route candidates still need
the authored key/proc/purpose review; a graph hit alone is not final eligibility.

All 135 remaining records are now classified in the assignment document:
**79 independent additions and 56 exclusions**. The 115 existing catalog rows
and the original 104-zone queue are retained. No shared-origin grouping is added.
All new areas have a source-reviewed entry and encounter witness. Disconnected,
closed, control/map, staging and private infrastructure records have explicit
exclusion reasons; owner exclusions remain intact. #300/#1350 are independent
counterparts, not merged with #44/#13.

Local audit artifacts (research only, not release inputs):
`bin/tests/named-set-roster-audit.py` reads the isolated generated world and writes
`bin/tests/named-set-roster-audit.{json,txt}`; `bin/tests/roster-detail.py <IDs>`
prints route and encounter witnesses. Roots use declared mortal hometown/tutorial
arrivals and eight explicit native planar destinations; guessed teleport targets
are not entry evidence. The final route audit folds reset door states, requires
obtainable keys for locked pickproof doors and obtainable native switches for
blocked walls. The assignment document records the important gate dependencies.
Full Ailvio/Wutvr outposts qualify through native onboarding routes and ordinary
wolf encounters. Orog vipers disperse from staging room 45909 to reachable caves;
their level 10 satisfies the hometown drop cap. The permanent catalog regression
now reconciles all 354 active zone IDs against the reviewed document, so final
coverage does not depend on ignored audit artifacts.

### Restore naming for four existing sets

**Outcome:** source review confirms independent playable areas for #87 Gibberling
King, #370 Crystalspyre Mountains, #676 Taliccicopiid and #824 Temple of the Sun.
Their authored headers now use `&+g…&n` without changing the visible wording.
The [assignment document](named-zone-set-first-pass-assignments.md#existing-plain-title-set-areas)
records concrete entrances, reset encounters and the Gibberling entry key.
Existing tiers remain Spirit Ward 3/Haste 5; Endurance 3; Endurance 4; Vitality 6,
respectively. At that checkpoint the catalog remained **115 rows / 206 tiers /
64 effect IDs**; the subsequent data chunk is described below.

**Non-goals/files/ablation:** four authored `.zon` title lines, existing tests and
the continuation documents only. The generator's color/naming rules, RNG, drops,
spawn pool, reset commands, item identity format and spell thresholds are
unchanged. These four need no new catalog or shared-set abstraction.

**Proof passed:** the real generator consumes their actual authored titles and
checks successful naming/origin, failed rolls and fixed-material exclusion.
The 1,480 frozen equipment cases and all RNG sentinels remain identical. Origin
tests include all four IDs and legacy names/clones; native membership and tier
dispatch cover 2/3/4/5/6 pieces, HP and removal. Isolated `make world` changes
exactly the four title strings: all reset bytes and the other six generated
outputs match the previous world. No generated outputs in the working checkout
are edited. Commands:

```sh
python3 tests/async/test_random_equipment_golden.py
python3 tests/async/test_named_set_origin.py
python3 tests/async/test_named_set_membership.py
python3 tests/async/test_named_set_catalog.py
```

These are source/generator/membership checks. Actual full gameplay and storage
journeys remain in the final gates. No deployment or release has occurred.

### Reviewed catalog installation (native catalog gates passed)

**Outcome:** the implementation/test catalog now contains **298 rows, 389 tiers
and 106 effect IDs**: all 115 original rows plus 104 original additions and 79
wider-review additions. Every new row has one tier; the 183 additions comprise
175 three-piece, six five-piece and two six-piece requirements. All original
zone/effect/threshold rows and roaming data remain byte-for-byte unchanged.
The 21 newly approved plain-title areas receive color/reset codes only; their
visible names, resets and topology are unchanged.

**Files/ablation:** extend the existing `named_sets.c` array, authored zone headers
and existing tests. The assignment document is the reviewed data manifest; no
runtime roster service, grouping layer or effect adapter is added. The single
report formatter now explains Guardian Spirits, Virtue and light exclusions.

**Passed:** both backend builds; catalog/manifest reconciliation of all 354 active
records; all 1,480 golden equipment cases/RNG sentinels and actual title checks;
membership/tier dispatch; all 50 real effect handlers and conditional cases.
The documented reset witnesses also pass an upper-bound check against every
preceding M/F reference to their prototypes; Orog dispersal is checked separately.
Isolated world regeneration changes exactly 21 additional title strings, with
all resets and the other six generated outputs identical. A full private flat-file
world boot (no minimal/specials/ferry suppression) reaches the game loop, creates
and saves a synthetic character. The normal player's disabled-Redis `namedreport`
pages through all 298 IDs exactly once and includes the conditional notes.

**Review readiness:** these rows are in the local implementation/test build,
not deployed. The required native wear/HP/ordinary-cast/save/reboot catalog gates
now pass through #733/#734 and #732 is ready for review. Source/fixture evidence
did not replace these journeys. Remaining storage, MariaDB gameplay, live Redis,
help/publication and rollback work is still required. Do not mark #706 or this
goal complete.

Continuation runtime: `bin/tests/named-set-roster-world` contains the generated
full world, private flat-file authority in `state/`, and a synthetic `Taverek`
character created by `test_flatfile_combat_journey` helpers. Its test account
credentials come from that test module; no owner credentials were copied.
`bin/tests/run-named-full-boot.py` boots/reconnects without reseeding the authority
and writes `full-server.out` / `namedreport.txt`; its process is stopped after the
check. Do not delete/reseed this state to hide a failure. Continue using the native
`randobj eq <slot> 56 <count>` staff path in this isolated world and retain the
real generated item UIDs/origins. Tharnadia, Bloodstone, Forgotten Forest and all
seven identity cases plus their two counterparts now pass as recorded below.

### Native Tharnadia wear, ordinary cast and reboot journey

**Outcome/files:** `tests/async/run_named_set_wear_journey.py` uses the normal
full-world flat-file server, existing synthetic account, and native command /
GMCP item-selector paths. `named_set_journey_fixture.cpp` reads its saved authority
and prepares only the synthetic tester's level/base HP and unrelated stored buffs
while the server is stopped. It checks the private test path and character name;
it never creates, renames, rekeys, or edits generated item content. The high base
HP is a test buffer, not a balance claim. No product code changed in this chunk.

The initial native `randobj` batches produced 24 named #1325 items among 90
candidates. The runner selects HP/CON-clean head/body/leg pieces, retaining UIDs
`3068497`, `3068540`, `3068564`; two further native batches supplied hands/arms
UIDs `23068496`, `23068524`. Existing candidates are reused on subsequent runs.
Ordinary vision/protection bits remain unchanged;
pieces with built-in Armor are excluded so the set grant is observable.
Surplus gear is packed through native `load`/`open`/`put` into ordinary containers,
including nested backpacks, rather than being deleted or resetting the authority.
This preparation is needed because a staff inventory can exceed the mortal
item limit and correctly block `remove`.

**Native proof:** a level-56 Human Warrior gets **+0/+5/+10/+15 maximum HP at
2/3/4/5 pieces**. Armor starts at three; Endurance starts only at five. Native save
completion, disconnect/server restart and login retain all five exact UIDs,
#1325 origins and wear slots, restoring +15 HP and Endurance. Removing the two
extra pieces returns to +5 HP with Armor and cleans Endurance. Dropping below
three returns HP to baseline. The reserved origin is read from the real saved
item, not inferred from the name. Both the earlier three-piece reboot run and
the extended five-piece reboot run pass.

The native `quaff` of the existing Armor-only potion #39130 after a set grant
creates one ordinary Armor affect. Reapplying the set with that ordinary affect
already present covers the other order. Removing set support preserves the
ordinary affect and its duration; a further save/reboot retains it exactly once.
Set Armor is absent from the saved character affects before the potion. The
native item stream supplies current session-scoped selectors; a bare stored UID
is deliberately not accepted as a command selector.

**Run:** `python3 tests/async/run_named_set_wear_journey.py` from the repository
root. It compiles its small snapshot fixture and uses the already prepared
`bin/tests/named-set-roster-world` and `bin/tests/named-set-flatfile-server`.
The former is a normal isolated `make world` of the authored areas plus the
tracked `lib` tree, private state/journals/logs, and a generated test TLS certificate.
Initial character creation/seeding uses `test_flatfile_combat_journey` helpers;
do not reseed the existing authority when continuing. The runner reconnects and
preserves generated items on retries, saves `named-wear-result.json` and the last
session transcript, and always stops its own private server. Native transcripts,
authority and server logs stay ignored under `bin/tests/`.
The native run, `make -C src -j4`, fixture compilation with
`-Wall -Wextra -Werror`, C++ formatting, Python static checks and `git diff --check`
pass. The driver waits for actual HP transitions within a bounded deadline;
a fixed six-second cleanup delay was too short on a repeat run and was removed.

**Ablation/limits:** reuse the existing client, account, snapshot codec and native
generator. No gameplay debug command, persistence schema, test-only server option
or separate spell simulator is added. This proves Tharnadia's 2/3/4/5 thresholds,
Endurance cleanup and ordinary Armor ownership; it does not complete
Bloodstone/new-area or seven-zone journeys, cross-owner/storage gates, MariaDB
gameplay, live Redis, help publication or rollback. The area journeys below
complete #732's native catalog readiness gate; keep #706 and the overall goal open.

### Native area and identity journeys passed

**Outcome/files/proof:** extend `run_named_set_wear_journey.py` with the explicit
required zone cases, reusing its existing native client, generator, save/reboot
and UID/origin checks. Each case checks native report/inventory, HP and effect
thresholds, persistence and removal outside its generation zone. The first
cases are Bloodstone #740 (Battletide at five) and wider addition Forgotten
Forest #827 (Protection from Animals at three), followed by the seven repaired
zones and the #300/#1350 counterparts. No new gameplay mechanism or test
framework is needed. The snapshot fixture excludes built-in Armor and mutually
exclusive light/darkness bits from selected candidates so set activation is
observable; generated item content is unchanged. Commands take an optional
explicit zone ID, for example `python3 tests/async/run_named_set_wear_journey.py 740`.
Keep the existing private authority; previous candidates stay in native containers.

**Passed:** Bloodstone #740 has no Battletide at three/four pieces, grants it
at five with +15 HP, restores it after save/reboot, and cleans it below five.
Its native UIDs are `27068547`, `27068841`, `27069764`, `27069794`, `27069821`.
Forgotten Forest #827 grants Protection from Animals at three with +5 HP and
cleans it below three; UIDs `30068536`, `30068758`, `30069373`. Both normal
level-56 journeys run outside the generation zone, retain exact UIDs/origins/
wear slots across reboot, verify the native report/inventory, and confirm that
the transient effect was not stored as an ordinary character affect.

Evidence stays under `bin/tests/`: `named-zone-740.log`, `named-zone-827.log`,
the corresponding `named-zone-<id>-result.json` in the runtime, and per-zone
transcripts. The updated driver retains every session's transcript for later
cases. The identity-zone cases and a Tharnadia regression of the shared driver
ran serially through `bin/tests/run-named-identity-cases.py` and completed with
exit 0. The driver stops on the first failure and never reseeds the authority.
Native cases **#13, #44, #204, #808, #811, #814, #990, #300 and #1350 all pass**:
effect/HP threshold, report/inventory, exact UID/origin/wear-slot restoration and
removal. The final #1325 regression also passes all five-piece/ordinary Armor
checks through the shared driver, with new UIDs `60068526`, `60068799`,
`60069704`, `60069736`, `60069767`. The ordinary spell survives removal and
another reboot exactly once. Every private server process is stopped.

Later cases additionally assert that every earlier named UID/origin survives in
its native container tree after save/reboot, not just the currently worn pieces.
An aggregate check of the final real saved authority finds **478 unique named
UID/origin pairs across all twelve origins**, with no earlier marker lost during
the checked native nested-container saves/reboots. Per-zone result JSON and
complete session transcripts record each run. This is player/container proof;
cross-owner transfer, pets, corpses, lockers/chests, shops, saved-world paths and
MariaDB gameplay remain separate gates.

C++ formatting/fixture compilation, Python static checks, `make -C src -j4` and
`git diff --check` pass. #732 was marked ready for review after these native gates
passed; no implementation PR was merged, tagged or deployed.

The four previously plain-title existing sets' native journeys are now complete
in the following checkpoint. Next complete the cross-owner/storage and MariaDB
journeys, live Redis lifecycle, canonical help publication and rollback rehearsal.
Reuse the real generated items and the existing private authority.

### Existing-title native journeys passed

**Outcome/files/proof:** reuse `run_named_set_wear_journey.py` and its private
full-world authority for #87 Spirit Ward at three / Haste at five, #370
Endurance at three, #676 Endurance at four and #824 Vitality at six. Extend the
existing slot list with feet for the sixth piece. Vitality's real native handler
adds `4 * cast level`: six pieces reach the existing 56 cap, so the expected
gain is **+20 basic set HP plus +224 Vitality HP**. Both terms must disappear
according to their own support threshold on removal. The fixture excludes
built-in Haste alongside the existing Armor/light conflicts so #87's grant is
observable, without altering generated item contents. No product code, effect
adapter or new test framework is needed. Verify native generation from the
repaired titles, report/inventory, mortal thresholds, exact UID/origin/wear-slot
restoration, transient affect storage, removal, and all prior nested origins.
**Passed:** #87 activates Spirit Ward at three and Haste only at five;
removing the fifth piece cleans Haste while retaining Spirit Ward. Both are
transient across save/reboot. Its selected UIDs are `64068522`, `64068838`,
`64069531`, `64069559`, `64069590`. #370 Endurance at three passes with UIDs
`67068561`, `67068912`, `67069388`; #676 Endurance at four passes with UIDs
`70068512`, `70068767`, `70069456`, `70069482`. All three pass native report,
inventory, mortal wear/HP, reboot identity, removal and earlier nested-origin
retention. #824 also passes through six pieces with UIDs `73068568`, `73069023`,
`73069578`, `73069606`, `73069638`, `73069686`. Its native mortal maximum HP
observations are **1486 / 1491 / 1496 / 1501 / 1730**: the six-piece value is
baseline +20 set HP +224 Vitality. Save/reboot restores +244 total, removing the
sixth piece returns to +15 without Vitality, and full removal returns to baseline.

The serial `bin/tests/run-named-title-cases.py` finishes with exit 0. Per-zone
logs/results/transcripts use the same ignored locations as the earlier cases.
The final real saved authority contains **645 unique named UID/origin pairs
across sixteen origins**, retaining the earlier container-held items throughout
these reboots. All private server processes are stopped. The native runs,
fixture compilation, `make -C src -j4`, C++ formatting, Python static checks and
`git diff --check` pass. No product code, generated item content, production
state, release tag or deployment was changed.

**Transfer approach (implemented below):** use the existing character helpers with a second
synthetic account, retaining the current authority and real generated item UIDs.
Transfer named gear in native nested containers, then wear/save/reboot it under
the recipient. Keep the recipient free of the accumulated candidate pool so the
native `attributes` Armor Points comparison cannot be masked by the existing
armor/load caps. Compare the same worn gear after ordinary Armor and after
removing/reapplying set support to prove effective non-stacking, alongside the
already verified duration/source and saved-affect checks. Do not edit generated
item identity or provenance to prepare this journey.

### Native transfer and effective Armor journey passed

**Outcome/files/proof:** extract the wear runner's existing native I/O into
`tests/async/named_set_gameplay.py` for its two real callers; keep the case data
and assertions in the wear runner. Add `run_named_set_transfer_journey.py` for
two accounts and native nested-bag transfer, receiver wear/reboot and effective
ordinary Armor checks through `attributes`. Extend the snapshot fixture only
to the second synthetic character (PID 2, `Meranen`) and read-only inventory
coordinates; retain the PID/name/private-path guards. The only offline writes
remain tester level/base HP and unrelated stored buffs. Generated content,
UIDs and provenance are never prepared by editing snapshots. Use native bag
commands to archive starter gear and keep the recipient's Armor Points away
from the real caps. No product code, new server option or storage format is
needed. The shared-helper Tharnadia regression passes, including the full
five-piece/ordinary Armor path after the helper extraction.

The normal character-creation path created the second account `Namedguest` and
character `Meranen` (PID 2). Native commands archive starter gear, prepare the
two bags and make both testers visible. At the actual handoff both are level-56
mortals; native consent/give moves a cotton backpack inside the collector bag,
containing the original #1325 UIDs **`76068523`, `76068769`, `76069376`**. The
test checks that those UIDs leave PID 1 and appear only under PID 2. It verifies
the exact inner/outer/child parent links both after the give and after receiver
materialization/save on the next boot, then unpacks and wears them natively.
Another reboot preserves the exact origins, wear slots and wear flags.

The clean recipient's baseline maximum HP is **1475**, with +5 at three pieces.
Set Armor is absent from stored ordinary affects. After native potion Armor,
removing/reapplying set support leaves the same effective `attributes` Armor
Points, away from both caps, and another reboot retains exactly one ordinary
Armor with no duration increase. The first two successful runs observe **-63**
and **-64**; the final run with explicit post-load parent/slot comparisons
observes **-65**, constant within that run across reapplication and reboot.
The differing runs use separate native potion rolls. No expected item or spell
payload was installed through the snapshot fixture.

One preparation attempt exposed stale test selectors: repeatedly resetting
`Char.Items.Get []` could pick already queued pages from an older scope. The
shared reader now consumes the automatic stream's latest complete inventory /
equipment revision, including context/body identity, and returns all selectors
for one command from that same snapshot. The server correctly rejected the old
tokens; no product repair was needed. The authority was retained and the same
UID manifest resumed the test. A complete repeat also passes using the same
items after returning them through native commands, without reseeding.

**Run/proof:** `python3 tests/async/run_named_set_transfer_journey.py`; rerun the
existing wear runner directly for its shared-helper regression. Setup/result
JSON, complete transcripts and the qualification logs stay under the existing
ignored runtime / `bin/tests/` paths. The final real authority retains **751
unique named UID/origin pairs across both owners**, with no duplicate UID across
their complete inventories. All private servers are stopped. The native runs,
`make -C src -j4`, fixture `-Wall -Wextra -Werror` compilation, C++ formatting,
Python static checks and `git diff --check` pass.

This closes the native flat-file player/nested-container/cross-owner proof and
the effective ordinary Armor overlap check. Visible-name editing/cloning now
passes in the following checkpoint. Pets, corpses, lockers/private chests,
shops, saved-world paths, MariaDB gameplay, live Redis, canonical help publication
and rollback remain project gates.
No implementation PR was merged, tagged or deployed.

### Native visible-name editing and recursive cloning passed

**Outcome/files/proof:** add `run_named_set_edit_clone_journey.py` using the
existing shared native I/O and receiver. Native `string obj ... short` removes
the visible zone cues from the three original #1325 pieces. Native recursive
`clone obj` copies their two-level bag tree, minting new UIDs while retaining
the reserved origins. Verify names/markers, exact hierarchy after reload, clone
wear/cleanup, a mixed original/clone outfit and exact slots after another reboot.
The small native put helper is shared by its two actual callers. No product
code, item-metadata edit through snapshots, new storage format or server debug
option is needed. Keep the existing authority and record the clone UID manifest
for repeat runs.

**Passed:** the three original receiver UIDs `76068523`, `76068769`, `76069376`
now have plain verification helm/coat/leggings descriptions with no visible zone
cue. All keep explicit #1325 metadata. Native recursive cloning creates outer
bag `98069717`, inner bag `98069718` and named copies **`98069719`, `98069720`,
`98069721`**, all distinct from every previous UID. Both original and cloned
trees preserve their exact parent links, origins and edited names after receiver
materialization/save on reboot.

At mortal level 56, the three renamed copies grant **+5 HP and Armor** from the
1475 baseline. Removing the copied head piece cleans both; substituting the
renamed original head restores the same set, proving mixed original/copy
membership. A further reboot retains all six named items' exact origins, wear
slots and wear flags. No set Armor is saved as an ordinary affect. The final
authority holds **754 unique named UID/origin pairs** across both owners, with
all earlier identities retained. All private servers are stopped.

**Run/proof:** `python3 tests/async/run_named_set_edit_clone_journey.py` (exit 0),
`python3 tests/async/test_named_set_origin.py` (the focused native origin/legacy/
clone/storage checks pass), `make -C src -j4`, Python static checks, C++ formatting
and `git diff --check` pass. Setup/result JSON and full transcripts stay under
the existing ignored runtime. The put helper's implementation is unchanged;
it moved to the shared I/O module for the two callers. No product code changed.
Pets, corpses, lockers/chests, shops, saved-world paths, MariaDB gameplay, live
Redis, help publication and rollback remain required. No deployment occurred.

At this checkpoint Meranen owns the original and copied pieces: the original
head and copied body/legs are worn, the other three are carried, and the four
test bags are empty at inventory root. The current setup/result manifests and
snapshot fixture identify their UIDs without guessing names. For the next
storage proof, inspect the maintained `test_pet_restart_journey.py`,
`test_corpse_trap_restart_journey.py` and locker/shop journeys before adding
fixtures; keep these real marked items and the existing authority.

### Native pet-held named items passed

**Outcome/files/proof:** add `run_named_set_pet_journey.py` using the shared
native I/O, existing Meranen and original #1325 body item. Native `givepet`
creates an ordinary permanent cat; native put/give places the marked piece in
its backpack. Verify active pet restoration, exact child UID/origin/parent/slot
through two owner reboots, then use native order/give/get to recover and wear
the same item and verify another reboot. Extend the snapshot fixture with
read-only pet inventory coordinates, reusing its origin reader; no pet, item or
origin payload is seeded. No product code, new command or storage format is
needed. Two native restarts retain the active cat and exact marked child graph.
Animal NPCs intentionally ignore `drop`, so recovery uses the supported ordered
give. The first recovery also exposed the fixture's overly broad affect reset:
clearing achievement markers re-issued reward satchels and exhausted mortal
inventory slots. Preparation now clears spell/rest buffs while preserving all
internal tags, including achievements and cooldowns; existing reward bags are
retained inside another native container. No product defect was found here.

**Passed:** native `givepet` creates the active ordinary cat #74132. Backpack
`81069478` carries original body UID **`76068769`**, still #1325 with its edited
plain description, under the pet after two owner reboots. Exact inventory
parent/slot/origin rows are unchanged and hold reason remains none. Native
`order cat give backpack Meranen` returns it; get/unpack and wear restore +5 HP
and Armor from the recorded 1475 receiver baseline. Another reboot preserves
the exact returned origins, wear slots and flags. A complete repeat passes on
the same authority, with the same reward satchel UIDs across all reboots; the
fixture no longer re-issues level achievement gifts.

**Run/proof:** `python3 tests/async/run_named_set_pet_journey.py` and its repeat
finish with exit 0. `make -C src -j4`, fixture warning-clean compilation, Python
static checks, C++ formatting and `git diff --check` pass. Setup/results/logs
and full transcripts stay ignored under the existing runtime. The cat remains
an active empty permanent follower; the body is back on Meranen. All private
servers are stopped. This proves the flat-file pet inventory path; corpse and
other storage/backend gates remain separate. No release or deployment occurred.

### Native player-corpse named items passed

**Outcome/files/proof:** use the existing private authority, six real marked
pieces and Meranen for native death/corpse/loot/reboot. `run_named_set_corpse_journey.py`
packs the complete inventory tree natively, invokes the normal death pipeline
through staff kill, verifies corpse custody and origin values, reboots before
looting, checks the exact recovered graph and restores worn bonuses on another
reboot. The maintained flat-file inspector gains only the reserved origin value
in its existing corpse-item output; build it with
`python3 tests/async/test_flatfile_player_repository.py --build-inspector bin/tests/coin-death-inspector`.
No item payload is seeded and no product code or new storage API is needed.
Existing corpse state is inspected and resumed, never reset to hide a failed
attempt. The inspector now treats a genuinely absent catalogue as empty while
retaining errors for corrupt or unreadable state.

**Passed:** native staff kill enters the normal death pipeline for mortal
Meranen and persists all six original/copied UIDs with exact #1325 values in the
player corpse. Those UIDs disappear from the player. A full reboot restores
the corpse with the same six markers; normal owner looting releases corpse
custody and restores the **exact 14-item nested inventory graph**, keyed by
UID/vnum/parent UID/slot. The recovered original pieces restore +5 HP and Armor
from the 1475 baseline, and another reboot retains every named item's exact
origin, wear slot and wear flags. All **754** earlier named identities remain
unique across both players; no recovered UID remains in corpse custody.

The first loot attempt actually succeeded but the runner expected the old
per-item receipt; bulk corpse looting reports `Haul:`. Recovery resumed from
the observed saved player graph without manufacturing another death. The runner
now records verified corpse persistence before looting and recognizes that
completed recovery point. A subsequent fresh death-to-recovery run passes with
exit 0 under the corrected receipts. It requests real nested item selectors to
retrieve the three pieces individually, avoiding a full-inventory bulk unpack.

**Run/proof:** build the maintained inspector as above, then
`python3 tests/async/run_named_set_corpse_journey.py`. The saved-state recovery
and full fresh run both pass; inspector warning-clean build, `make -C src -j4`,
Python static checks, C++ formatting and `git diff --check` pass. Setup/result
JSON, corpse/resume/final logs and complete transcripts stay ignored under
the existing runtime. All private servers are stopped. No product code or
generated item payload was edited; no release or deployment occurred.

The six pieces are again under Meranen: originals worn and copies in the
outer container; the empty cat was dismissed by the normal death pipeline.
Next complete locker/private chest, shop/saved-world, MariaDB, live Redis,
canonical help and rollback gates using the retained authority and real items.

### Native public locker storage passed

**Outcome/files/proof:** add `run_named_set_locker_journey.py` using the real
original #1325 pieces in a native container. Native counter/enter/drop/leave
must persist the public account locker, then a reboot/get/leave restores the
exact UID/vnum/parent/slot graph. Verify empty locker custody and mortal set
activation plus another reboot. Extend the maintained read-only inspector to
list locker item coordinates and origin values. Reuse the corpse journey's
inventory-graph conversion in the shared helper. No product code or seeded
item payload is needed. Flat-file runtime explicitly does not offer private
chests (`locker_private_chests_available`); that active path remains a MariaDB
gate rather than a new feature to implement here.

**Setup failure retained:** the first runner accepted the entry cost line too
early. Even an overlord needs the fee; the bank rejected one copper and ejected
Meranen. The subsequent drop therefore put outer `81069607` on the ordinary
shop floor, not in locker storage. That floor was non-saving with Redis disabled;
after shutdown the tree has no remaining item payload in player, locker, world
or shop authority (only stale item-ownership entries remain). The lost sandbox
tree included copied UIDs **`98069719`, `98069720`, `98069721`**, four test bags
and four reward satchels. The three original marked pieces remained worn and
safe. The earlier pet/corpse/edit proofs describe their completed checkpoints;
the current retained named count is **751**, not 754.

The authority was not reset, the lost UIDs were not reassigned or fabricated,
and the failed setup/log/transcript remain under their original / `unfunded`
names. The funded runner uses the surviving originals and a new native bag.
It obtains the fee through native NPC currency transfer and verifies the
locker room after the cost receipt before permitting any drop. Its separate
`named-locker-funded-setup.json` keeps the failure evidence intact. This is a
test setup error and expected ephemeral floor behavior, not a named-origin
serialization defect; do not conceal it by claiming the old copies still exist.

**Funded case:** native `force Kieta give 1 platinum Meranen` funds the real
fee. New container **`125068524`** holds original UIDs `76068523`, `76068769`,
`76069376`; no lost UID is reused. Deposit claims them into
`account.namedguest.1.locker` and removes them from player custody. A reboot
retains all three #1325 markers and the exact four-item UID/vnum/parent graph.
Locker records use the unworn sentinel -1; this is checked explicitly and
normalized to the player snapshot's unworn 0 for graph comparison. The bag is
restored on the locker floor, so native `get collector` retrieves it.

The saved retrieval case passes: locker custody becomes empty, mortal wear
restores +5 HP/Armor from baseline 1475, and another reboot preserves the exact
origins, slots and flags. A fresh full funded cycle also completes with exit 0
under the correct entry validation, sentinel handling and floor retrieval.
Failed and funded manifests/logs remain separate under the ignored runtime.

**Run/proof:** build the maintained inspector, then run
`python3 tests/async/run_named_set_locker_journey.py`. The resumed retrieval and
fresh full cycle pass. `make -C src -j4`, warning-clean inspector/fixture builds,
Python static checks, C++ formatting and `git diff --check` pass. All private
servers are stopped; public locker custody is empty and the original three
pieces are worn by Meranen. The retained named count is 751 after the documented
unfunded setup loss; it does not include the lost copied items. No product code,
lost identity re-creation, authority reset, release or deployment occurred.

The following checkpoint covers disposable MariaDB/private chests. Preserve the
flat-file authority and its original UIDs; it is not reset or reused for SQL.

### Native MariaDB player and private-chest checkpoint

`run_named_set_mariadb_chest_journey.py` reuses the maintained disposable
MariaDB wrapper/bootstrap, native account creation and GMCP item commands.
Its full-world areas are the privately generated named-set world; its `lib`
and help sources come from tracked `HEAD`, excluding local account/player data.
Only synthetic level/HP and currency fixtures are set offline. All gear, origin
markers, UIDs, containers and custody movements come from native commands.

Two new accounts provide a mortal wearer and a staff helper at real bank #16590.
Native `randobj` in #1325 supplies three HP/CON-clean head/body/leg pieces.
The mortal journey checks two pieces give no HP/Armor grant, three give +5 HP
and active Armor, and removing them removes both benefits. SQL player metadata
retains the exact UIDs, #1325 origins and worn slots across reboot. Set Armor is
not serialized as an ordinary cast in `player_affects`.

Native funded locker entry checks payment success and the actual locker room.
The owner buys a password-protected private `vault`, stores the three marked
pieces in a native collector bag, closes it and leaves through the normal save
barrier. `locker_items` and `locker_item_extra_descr` must contain exactly the
four-item UID/vnum/parent/origin graph; player custody must exclude that tree.
After reboot, native owner open/retrieval empties the private chest and restores
that exact graph. Native unpack/wear and a final player reboot must restore the
same origins, equipment slots, Armor and +5 HP.

**Ablation:** one focused SQL journey, reusing existing authority and command
helpers. No product code, schema, backend adapter or generalized runner change.
Artifacts and transcripts remain in a unique ignored `bin/tests/named-set-mariadb-*`
directory. A failed run also dumps its disposable database before cleanup; the
first SQL-output parser failure is retained separately. No old fixture UIDs are
fabricated or replaced, and the existing flat-file authority remains untouched.

**Passed:** two complete native player/chest/retrieval/reboot runs. The final
run includes explicit two-piece, active-spell and no-saved-Armor assertions;
its `bin/tests/named-set-mariadb-_rer4ev4/evidence.json` and transcript retain
UIDs `1071684`, `1072149`, `1072594`, bag `1072745`, baseline HP 1486 and the
exact original SQL equipment slots. The first parser-failure artifacts remain
in `named-set-mariadb-hbcsnv8s`. Python compilation and `git diff --check` pass.
All private servers are stopped; the disposable schema/container are removed
through the existing wrapper. The flat-file authority remains at its previously
disclosed 751 retained named items. Command:

```sh
tests/async/with_disposable_mariadb.sh python3 tests/async/run_named_set_mariadb_chest_journey.py
```

Next complete shop/saved-world paths on both active backends, live Redis report
lifecycle, canonical help publication and compatibility rollback. The checklists
below now distinguish already proven implementation from these remaining gates.
No release, merge or production deployment has occurred.

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

- [x] Recheck #706, the active [area registry](../../areas/AREA), and the two
  companion documents against the implementation checkout. Preserve all 104
  planned zone IDs, the original 42 choices, and the 62 reuse choices. The
  reuse pool has 50 effects: the 42 newly selected effects and eight existing
  simple effects. Every initially unused candidate had two or three proposed
  homes after those two passes; 60 of the 62 reuse choices favored an effect
  with one home at that pass's start. Wider additions and final home counts
  are now recorded separately.
- [x] Give each of the 104 additions one effect tier. Start the balance review
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
  Native grant/conditional qualification now passes as recorded above; derived
  character totals and the full gameplay gates remain open.
- [ ] Preserve the Shaman restriction for Guardian Spirits (#780 and #422),
  Virtue's alignment condition, and light/darkness exclusions. Describe those
  restrictions in player-facing help/report notes so a set is not presented
  as granting a universal benefit when its spell is conditional.
- [x] Complete the wider area review required by #706: classify remaining
  broad-screen candidates and excluded plain-title areas as independent set,
  explicitly shared set, or excluded with a reason. Check repeatable eligible
  kills and real player access, including secret/locked paths and gated planes.
  The 104-zone roster is a confirmed work queue, not the final world denominator.
  Add further eligible areas to the same assignment document using the simple
  effect pool; reconcile the totals again.

The roster exclusions #380, #384, #536, #870, and #1422 remain recorded unless
new evidence and a content decision change them. The four existing plain-title
set zones (#87, #370, #676, #824) are now source-reviewed independent playable
sets with authored title fixes; their native gameplay journeys pass. Production
publication remains an owner-authorized deployment gate.
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

The original 104-zone cohort reconciled to 219 rows / 310 tiers / 106 effect IDs.
The completed wider review adds 79 areas: the implementation/test catalog now
reconciles to **298 loaded rows / 389 tiers / 106 effect IDs**. The frozen digest
still proves every original row survives unchanged.

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
- [x] Validate the complete stored marker before materialization. An absent
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
- [x] Before removing a shared spell, reconcile all currently qualifying worn
  sets. The spell must remain supported while another set still qualifies,
  without stacking duplicate buffs merely because two zones use it. Verify
  ordinary casts both before and after the set grant; preserve their independent
  durations and source ownership. Keep any ownership helper limited to these
  demonstrated set/cast collisions.
- [x] Preserve existing timed effects and their reapplication constraints.
  Re-equipping, swapping the selected item, or alternating two sets must not
  create unintended fresh grants or bypass cooldowns. Trace linked/group
  effects already present in old sets while retaining the new simple-effect scope.

## 6. Install the catalog and publish one consistent report

- [x] Add the 104 assigned rows only after ID membership and cleanup pass their
  focused regressions. Use the assignment document as the mapping authority,
  including independent Barovia/Barovia Continued IDs that intentionally reuse
  Lifelust. Add any further zones accepted by the wider review with recorded
  mappings and updated counts.
- [x] Make Redis-cached and uncached `namedreport` use the same catalog and
  formatting path. Include zone IDs, piece requirements, conditional-effect
  notes, and existing cooldown markers. Replace fixed-size concatenation with
  bounded/growing output so the expanded roster is complete and paginates safely.
- [x] Update the staff diagnostic to traverse the complete real catalog and
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

- [x] Finish the reviewed eligibility roster with independent/shared/excluded
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
