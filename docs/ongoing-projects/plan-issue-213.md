# Issue #213: evil onboarding implementation plan

Tracking: [Duris #213](https://github.com/LuminariMUD/Duris/issues/213).
Implementation branch: `branch/issue-213-evil-onboarding`.
Status: planning only; no gameplay changes or acceptance results are claimed here.
Revised October 23, 2026 for the issue's approved Firbolg/Ogre eligibility decision;
the previous tutorial exclusions are superseded.

Evidence baseline: fetched Duris master
[`af15e38c47fa1bc7f9e138fe1cc2b5aa63c35c4a`](https://github.com/LuminariMUD/Duris/commit/af15e38c47fa1bc7f9e138fe1cc2b5aa63c35c4a)
on October 19, 2026. DurisWeb integration was checked against fetched master
[`18261c35c6fe0c126c6adee28e258f68124604ba`](https://github.com/LuminariMUD/DurisWeb/commit/18261c35c6fe0c126c6adee28e258f68124604ba).
The inspected web creation files are unchanged from its local checkout. Duris
master advanced by the #216 locker-weight fix during planning; that diff was
reviewed and does not change the onboarding paths documented below.
Master [`b03055188`](https://github.com/LuminariMUD/Duris/commit/b03055188d2979995ff51b435b4fd52dad636eae)
was merged on October 23, 2026. This onboarding plan now lives in
`docs/ongoing-projects/plan-issue-213.md`; master's shared `plan.md` and
[the #166 Hatred journey plan](plan-issue-166.md) are preserved unchanged.
The source inventory below describes the October 19 baseline; the master merge
is not fresh gameplay qualification. Recheck those source details before
implementation.

## Outcome and locked scope

Implement the issue's locked decisions, which supersede its original proposals:

1. No player loses death XP or levels while below level 30, regardless of race,
   racewar side, or tutorial eligibility. At 30, existing applicable death
   penalties resume. This is death protection, not immunity to other XP costs.
2. Reaching or crossing 30 produces a prominent, bold, ALL-CAPS warning that
   death can cost XP and levels, including a single award granting several levels.
3. Duplicate Plane of Life as **Plane of Chaos** and Outpost of Ailvio as
   **Wutvr**. These are final names. Preserve layout, lessons, objectives,
   encounters, mechanics, difficulty, reward quantities/power, and progression.
   Plane of Chaos receives minimal Chaos naming/theme substitutions. Wutvr
   changes named characters and their races, Ailvio references, and only essential
   faction wording; its environment and other prose remain the same.
4. Every evil-side creation character, including Ogre, gets its existing racial
   hometown plus Wutvr and Plane of Chaos. Ogre retains Faang. This includes
   evil-side selections of Thri-kreen, Minotaur, and Tiefling; tutorial eligibility
   follows the chosen racewar side. Preserve existing race/class availability
   restrictions; a restricted race is not enabled by this change.
5. Firbolg remains Good, retains Ugta, and gains Outpost of Ailvio and Plane of
   Life. Other good-side choices stay unchanged. No race gains opposite-side
   tutorials or arbitrary Shady/Tharnadia access. Firbolgs and Ogres receive the
   same universal death protection and level-30 warning as all other races.
6. The optional evil route is Plane of Chaos -> Wutvr -> the racial hometown,
   including Faang for Ogre. Firbolg follows Plane of Life -> Ailvio -> Ugta.
   Choosing Wutvr/Ailvio skips the first stage; choosing the racial hometown
   skips both. Departure from either second-stage tutorial updates home,
   birthplace, and original birthplace using the existing racial-home behavior.
   Shady is only the racial destination where it already applies.
7. Terminal and web creation must offer and enforce the same choices. Existing
   tutorials and racial hometowns retain their behavior.

Non-goals: no hometown aggressive-mob removal, relocation, or weakening; no
universal Shady/Tharnadia option; no Firbolg/Ogre balance changes; no relocation
price change; no new quests or tutorial redesign; no map connections; no changes
to global racial XP modifiers. “Plane of Chaos” is an area name, not activation
of the separate CHAOS game mode or its accelerated starting grants.

## Source inventory at the October 19 baseline

### Death and level advancement

- [`gain_exp()`](../../src/world/limits.c#L1372) currently exempts only
  `IS_RACEWAR_GOOD` from `EXP_DEATH`. The property
  [`exp.goodieDeathExpLossLevelThreshold=30.000`](../../lib/duris.properties#L792)
  supplies the configured cutoff, but the call's missing-property fallback is
  20. Both paths must agree on 30 after the change.
- [`die()`](../../src/combat/fight.c#L2546) has a separate Lich path calling
  `lose_level()` and scaling residual XP. Changing only `EXP_DEATH` would leave
  that path unprotected. Keep the Lich calculation unchanged at/above 30.
- [`notify_level_advancement()`](../../src/world/limits.c#L616) already receives
  the previous level. Ordinary XP, Illithid advancement, `advance_level()`, and
  bulk `advance_to_level()` converge on it. Its single-level branch currently
  returns early; adding a warning only after that return would miss 29 -> 30.
  This is the existing notification path to extend, without a new saved flag.
- The existing death path supplies the actual XP loss to later death handling.
  Preserve zero loss below the cutoff so corpse/resurrection bookkeeping cannot
  credit XP that was never lost.

### Creation and hometown resolution

- [The playable roster and restrictions](../../src/core/constant.c#L1580) and
  [`avail_hometowns`](../../src/core/constant.c#L1792) establish the current
  choices. Ordinary evil-only races are Drow, Duergar, Ogre, Troll, Orc,
  Githyanki, Goblin, Kobold, and Drider. The three side-selectable races are
  Thri-kreen, Minotaur, and Tiefling.
- Among normal good-only races, only Human and Githzerai have Tharnadia.
  The other non-Firbolg good races have their own racial home plus the two good
  tutorials. Firbolg had Ugta only at that baseline; the approved scope above
  adds its good tutorials. Shady's creation row is Orc-only.
  Comments in `defines.h` are historical and are not the eligibility authority.
- [Terminal selection](../../src/account/nanny.c#L3029) and
  [choice counting/display](../../src/account/nanny.c#L3277) currently consult
  only race. Both class-selection and alignment-selection paths call
  `find_hometown()`; changing just the printed menu would leave automatic
  single-choice routing wrong.
- Terminal selection matches the first letter of a town's name. **Payang and
  Plane of Chaos collide on P for evil Thri-kreen.** Use an explicit C key for
  Plane of Chaos and W for Wutvr; preserve existing keys and full displayed names.
- [Web hometown listing](../../src/net/ws_handlers.c#L2474) takes only a race.
  [Creation](../../src/net/ws_handlers.c#L2264) accepts any supplied in-range
  hometown ID without checking `avail_hometowns`. The final submission therefore
  needs authoritative eligibility validation, not only a filtered listing.
- [`find_starting_location()`](../../src/account/nanny.c#L3345) takes a hometown
  ID and returns a room VNUM through `GET_HOME`. Its early negative-alignment
  Tiefling override sends the character to Arachdrathos regardless of an explicit
  tutorial selection. Explicit new tutorial choices must bypass that override;
  default/direct racial-home behavior and final tutorial departure must retain it.
- [`HOME_*` IDs](../../src/core/defines.h#L1084) currently end at 24.
  [Creation guild locations](../../src/core/constant.c#L1991) use room 29201 for
  Ailvio and 22800 for Plane of Life. The separate `hometown[]` entries are
  29317 and 22806: do not confuse a generic home/coffin room with the entry room.

### Authored content and compiled behavior

The active [`areas/AREA`](../../areas/AREA#L115) includes `newbie2` and
`newbie`. Counting record headers in those authored files gives:

- Plane of Life: 7 rooms, 3 mobile templates, 10 object templates, one zone file.
- Ailvio: 117 rooms, 105 mobile templates, 133 object templates, 32 quest
  controller records, 8 shops, one zone file. The quest file has 4,142 lines;
  32 controller records must not be presented as 32 independent quests.
- Together these are ten source files under `areas/{wld,mob,obj,qst,shp,zon}`.
  Neither area currently has an authored trigger file.
- A read-only scan using the existing room parser found no ordinary exits from
  Ailvio to another active area, or from other active areas into Ailvio.
  Its departure is a compiled object procedure, not an overworld edge.

The necessary bindings are concrete:

- [`stream_of_life()`](../../src/specs/specs.object.c#L8895) gates on
  `TAG_LIFESTREAMNEWBIE`, heals, and moves to hardcoded room 29201.
  [`newbie_paladin()`](../../src/specs/specs.mobile.c#L11272) clears that tag,
  gives object 22804 once, and contains good-side dialogue.
- [`newbie_portal()`](../../src/specs/specs.object.c#L13132) calls
  `find_starting_location(ch, 0)`, updates both birthplace fields, and teleports
  home. This is the final-exit behavior to reuse.
- [Assignments](../../src/specs/specs.assign.c#L205) bind bandaging and spell-ups;
  other bindings in that file cover the guide, two signs, stream, two pet shops,
  departure portal, and two inns.
- [Ailvio procedures](../../src/specs/specs.ailvio.c#L27) hardcode map 29201,
  quest objects 29220/29221, NPC names, and the bandage target
  `VMOB_AILVIO_INCAPACITATED`. Duplicating files alone cannot produce working copies.
- [Starter-kit selection](../../src/account/nanny.c#L888) recognizes Ailvio only
  at room 29201 and [adds item 29319](../../src/account/newbie_kit_plan.c#L1733).
  A Wutvr direct start needs the corresponding copied item without changing
  race/class starter kits or giving a second kit during tutorial progression.
- [Mobile loading](../../src/world/db.c#L2160) and
  [XP modifiers](../../src/world/limits.c#L926) consult NPC race. Identical numeric
  area fields alone do not establish identical difficulty/rewards after a race
  substitution. [Shops](../../src/economy/shop.c#L733) also have race restrictions.
- [`areas/renumber`](../../areas/renumber) only handles world room IDs and their
  exits. It does not remap mobile/object/quest/shop/reset references.

### Required web-client integration

DurisWeb's
[`MudCharacterCreate.vue`](https://github.com/LuminariMUD/DurisWeb/blob/18261c35c6fe0c126c6adee28e258f68124604ba/frontend/src/components/mud/chargen/MudCharacterCreate.vue#L212)
requests hometowns immediately when race is selected, before a neutral race's
alignment step. Its
[`getHometowns()`](https://github.com/LuminariMUD/DurisWeb/blob/18261c35c6fe0c126c6adee28e258f68124604ba/frontend/src/composables/useMudConnection.ts#L980)
sends only `{race}`. A server-only patch cannot make its neutral-race menu correct.
The companion web change is part of #213 completion, even though its eventual
code/PR belongs in DurisWeb. No frontend implementation is included in this plan
publication.

### Claims not established by these checks

The original 12-versus-300+ aggressive-mob totals, comparative racial strength,
and live first-hour outcomes were not reproduced. No such balance survey is
needed now that the owner explicitly retained those mobs. Repository
[`price.home.plat`](../../lib/duris.properties#L2478) is 500 and
[`do_home()`](../../src/cmd/actnew.c#L4078) uses it; this is not a reading of
production configuration. No live server, loaded world, or gameplay journey was
used to validate this plan.

## Implementation sequence, files, and proof

### 1. Make the death cutoff universal and warn at the transition

Files: `src/world/limits.c`, `src/combat/fight.c`, the existing declaration
header needed by those callers, `lib/duris.properties`, and the DEATH entry in
`lib/information/help_index` and `help/duris_help_parsed.hlp`. Verify the active
help publication path for each persistence backend when delivering the help.

- Reuse the existing cutoff property for compatibility; document its legacy
  name as universal and set all missing-property defaults to 30. Use one small
  shared cutoff/protection function for the death paths and warning. Do not add
  another knob, parallel policy, or schema migration.
- Gate the Lich penalty as well as ordinary `EXP_DEATH`. Do not return early
  from the whole death handler: corpse creation, normal respawn, and other
  existing death behavior still run.
- Extend the existing consolidated level notification using
  `previous_level < cutoff && current_level >= cutoff`. Emit once per upward
  crossing, including a later re-crossing after losing a level, rather than on
  every award or login. Keep the existing player/morph recipient handling.
- Use the existing bold output markup, a separated warning block, and ALL CAPS:
  **WARNING: YOU HAVE REACHED LEVEL 30. DEATH CAN NOW COST YOU EXPERIENCE AND
  CAUSE YOU TO LOSE LEVELS!**
  If the existing property is configured differently, interpolate that same
  cutoff in the warning; do not print a different threshold from the policy.
  Plain-text clients retain the complete uppercase warning and spacing.
- Preserve ordinary penalties, Lich residual calculation, arena/staff handling,
  and existing hardcore rules at/above the cutoff. Update current help where it
  describes universal death loss; leave historical news entries as history.

Proof: execute ordinary and Lich death paths at levels 1, 2, 29, 30, and 31,
with good/evil/other racewar sides and Ogre/Firbolg included. Below 30 assert
unchanged XP/level and zero recorded loss; at 30/31 assert the existing
applicable loss, including a case that actually delevels. Verify corpse and
resurrection accounting. Exercise 28 -> 29, 29 -> 30, 28 -> 31, 30 -> 31,
re-crossing 29 -> 30, and bulk advancement; capture notification count, wording,
recipient, and formatting. Check normal XP rewards, direct advancement, and
unchanged level-cap behavior.

### 2. Produce faithful authored copies and remap their references

Files: new `areas/wld/chaos_intro.wld`, `areas/mob/chaos_intro.mob`,
`areas/obj/chaos_intro.obj`, `areas/zon/chaos_intro.zon`; and
`areas/{wld,mob,obj,qst,shp,zon}/wutvr.*`, plus `areas/AREA`.
Names here are source filenames; displayed names remain Plane of Chaos and Wutvr.

- Refresh master before allocating IDs. Inventory all authored entity namespaces
  and active sources, reserve collision-free room/mobile/object/zone ranges, and
  record an explicit source-to-copy mapping with the focused test fixture.
  No guessed range is reserved by this plan.
- Copy the ten files, remapping only typed references: record IDs, room/zone
  bounds, exits and keys, portal values, mobile/object spawns, containers,
  equipment, quest controllers/actions/rewards/teleports, shopkeepers/rooms/
  inventories, and any embedded references actually present. Keep intentional
  external references to shared supplies/services unchanged and list them.
  Do not use global numeric replacement or assume the room-only renumber tool
  handles the other formats.
- Apply the minimal text/name/race mapping consistently to visible prose,
  keywords, ask/tell targets, signs/maps, quest dialogue, and compiled messages.
  Check color-interleaved and hyphenated spellings such as Ail-v-io; preserve
  color formatting. Do not rewrite unrelated lessons or historical prose.
- Preserve every non-theme mechanical field: levels, hit/damage dice, armor,
  affects, skills, item stats, reward counts, prices, quest conditions, reset
  counts/chances/timing, zone difficulty, and topology. Make only necessary
  evil-side access substitutions in copied faction/race restrictions.
- Compare loaded counterparts with controlled RNG and the same acting
  character/configuration. Check derived combat stats, racial abilities/
  resistances, aggression, equipment usability, victim-race XP factors, and
  actual reward effects. Choose race replacements that retain behavior first;
  if a replacement needs compensation, keep it local to the copied content
  using existing mechanisms and prove equality. Do not change global races,
  original templates, or accept a difficulty/reward drift as “just a reskin.”
  Existing player racial XP modifiers remain in force; comparing different
  player races' XP totals is not a content-parity test.
- Keep the copies disconnected from the ordinary world exactly as the originals
  are, except for the required tutorial/exit routing. Preserve original source
  files byte-for-byte.

Proof: a focused area-parity check normalizes only the explicit ID/name/race/
essential-faction substitutions, then compares all remaining records and fields.
It must reject a changed reward, damage field, broken reference, duplicate ID,
or altered exit. Check all 32 quest controller records and all eight shops,
not just the guide. Run `make world`, validate the generated records/references
as well as authored files, and boot the copies. Generated `areas/world.*`,
lookup files, and binaries remain uncommitted.

### 3. Wire the existing tutorial procedures and creation rules

Files: `src/core/defines.h`, `src/core/constant.c`,
`src/core/prototypes.h`, `src/account/nanny.c`,
`src/account/newbie_kit_plan.{c,h}`, `src/net/ws_handlers.c`,
`src/specs/specs.{assign,object,mobile,ailvio}.c`, relevant
`src/world/vnum.{mob,obj}.h` constants; other indexed consumers only when the
new entries require a concrete adjustment.

- Append two hometown IDs after the existing range; never renumber old IDs.
  Extend names, eligibility rows, generic home rooms, and every class's guild
  entry room. Audit `hometown_arena`, justice/auction storage, training-dummy
  bootstrap, mail, and room-to-town lookup for new-index handling. Preserve
  existing indexing conventions and tutorial defaults; do not add services
  merely because their tables exist.
- Share one small race/side/hometown eligibility predicate between terminal
  choice counting, display, selection, web listing, and web submission.
  Preserve existing racial hometown rows. Add Firbolg eligibility to the existing
  Ailvio and Plane of Life rows; the two appended evil tutorial choices include
  Ogre. Enforce the selected side for all tutorial choices, including existing
  good tutorials, and reject cross-faction access. Resolve side through existing
  authoritative creation rules, not a client-supplied faction boolean.
- Keep forced/default racial-home resolution distinct from creation choices.
  Ensure both terminal creation entry paths use the side-aware choice count,
  with unique C/W keys for the additions. Audit callers such as staff newchar
  so an existing race-only/default call cannot accidentally select a tutorial.
- Allow explicit new tutorial selections to survive Tiefling's starting-room
  override. Preserve its existing Arachdrathos default/departure semantics and
  all other racial/class starting rooms.
- Validate web submissions before character persistence/kit grants. Reject a
  supplied nonnumeric, fractional, out-of-range, zero/Nowhere, wrong-side, or
  otherwise unavailable home, including evil tutorials for Firbolg and good
  tutorials for Ogre. Preserve the existing omitted selection default, but
  derive it from allowed existing racial choices.
  Keep race/class enablement and account racewar admission checks in force.
- Extend `get_hometowns` to accept the selected alignment for side-selectable
  races. Fixed-side races remain derivable from race alone. Before a neutral
  side is selected, a legacy race-only request may return only its existing
  racial choices; it must not expose side-dependent tutorials. Include enough
  race/side context in the response to discard stale results.
- Reuse `TAG_LIFESTREAMNEWBIE` for the equivalent first-stage gate. Route by
  the bound copy's mobile/object ID for guide text, sword reward, stream
  destination, and map/quest objects. Reuse shared sign, spell-up, bandaging,
  shop, inn, and final-exit behavior; parameterize only actual differences.
  Do not fork whole procedures or introduce a general tutorial framework.
- Add cloned assignments for the guide, signs, stream, departure portal, map/
  search objects, bandage pair, four spell-up mobiles, two pet shops, and inns.
  Ensure renamed ask targets still match and copied bandaging checks the copied
  victim. Reuse the current one-time guide reward; do not grant another kit.
- Select the copied equivalent of item 29319 for direct Wutvr creation through
  the existing kit planner and readiness/template checks. Preserve the current
  distinction between starting in an introduction and entering it later.
- Plane of Chaos exits into Wutvr. Wutvr's existing-style portal resolves the
  racial destination and updates all three home fields. Preserve original
  intermediate-stage respawn semantics; final departure must persist across
  death, relog, and restart. Firbolg's Plane of Life -> Ailvio -> Ugta
  route must use the same persistent racial-home semantics.

Proof: cover every currently enabled evil race, including Ogre, and every
permitted class at the eligibility/start-room level. Cover Firbolg's three good
choices, both sides of each neutral race, disabled races, and all other good
races' existing choices. Assert both accepted choices and rejected opposite-side
tutorials in terminal and web creation; compare their invalid-submission behavior.
Check Payang and Plane of Chaos are independently selectable. Exercise both explicit tutorials for evil
Tiefling and verify its eventual racial destination. Test copied proc dispatch
and rewards through real commands, plus original-guide/kit regressions.

### 4. Complete web parity and player journeys

Required companion DurisWeb files:
`frontend/src/types/mud.ts`,
`frontend/src/composables/useMudConnection.ts`,
`frontend/src/views/MudClientView.vue`,
`frontend/src/components/mud/chargen/MudCharacterCreate.vue`, and the hometown
state in `frontend/src/stores/mudStore.ts` where needed.

- Carry selected alignment through the existing event/request chain. Refresh
  hometowns after race/side changes; clear an invalidated selection, ignore
  stale responses, and prevent skipping the hometown step while its current
  options are pending. Do not duplicate the eligibility policy in Vue.
- Replace Ogre/Firbolg's old automatic single-hometown flow with their three
  eligible choices in terminal and browser creation. Preserve automatic flow
  only where a race/side still has one eligible hometown. Prove back navigation
  and switching neutral alignment cannot retain Wutvr/Plane of Chaos on good
  side, retain Ailvio/Plane of Life on evil side, or suppress eligible tutorials.
- Use the current text/ANSI output rendering for the warning. Verify bold
  appearance and complete uppercase text in the actual web terminal and an
  ANSI terminal. Existing rendering support is a reason to test first, not to
  add a new warning dialog.
- Keep the companion change/PR linked to Duris #213. Server protocol and client
  changes must be integrated before claiming web acceptance; server-handler
  unit tests alone do not close this work item.

Journey proof uses disposable servers/accounts and the generated authored world,
not replacement toy tutorial rooms. Reuse the lifecycle/client patterns in
[`test_creation_prompt_journey.py`](../../tests/async/test_creation_prompt_journey.py)
and [existing persistence journeys](../../tests/async/run_innate_hatred_journey.py).
Exercise terminal and actual browser creation, direct racial start, direct Wutvr,
and the complete Plane of Chaos -> Wutvr -> racial-home path. Also exercise
Firbolg's direct Ailvio and full Plane of Life -> Ailvio -> Ugta routes. Include:

- Gate refusal before the lesson, one successful lesson reward, repeat ask,
  signs/buffs, map request, search quest, bandage reward, shops/pets, inn, and
  each distinct quest action/reward type represented in the full controller
  inventory. Confirm a reset leaves the route and services usable.
- Representative melee and caster classes, Ogre, Firbolg, an additional evil-only
  race, all three side-selectable evil races, and another good original-tutorial
  control. Verify both oversized races can traverse every required passage,
  interact with guides/quests/shops, use required equipment, and complete all
  lessons with the intended difficulty and rewards. Make only supporting
  compatibility changes required for those paths; preserve existing racial
  balance and other races' tutorial behavior. Pair journey coverage with
  exhaustive eligibility and content parity.
- Death before departure, final home/birthplace/original-birthplace values,
  death after departure, rent/relogin and cold restart on flat-file and MariaDB
  backends. Recover mid-tutorial and check completion state/reward count.
- Actual threshold crossing and protected/unprotected deaths with saved
  XP/level readback, plus malformed web selections producing no persisted
  character or starter grant.

## Ablation decisions

Keep the shared cutoff and eligibility helpers: each has multiple real callers
whose divergence would break the locked behavior. Reuse existing tutorial
procedures, tag, kit planner, output formatting, world generator, and disposable
journey support. Keep content/reference parity and actual gameplay proof:
neither static equality nor a successful boot proves renamed quests, race
effects, web selection, or persisted home routing.

Drop a generic cloning engine, tutorial registry, new saved warning state,
new database tables, new telemetry/balance study, global NPC rebalance, fixed
soak delay, full burn-in, and unrelated cleanup. A focused remap/parity fixture
is sufficient; the existing authored source copies are the runtime inputs.
No new policy decision or approval stage is needed to implement these locked
requirements. Production operations remain separately authorized.

## Verification commands and completion gates

Planning publication checks only: inspect current issue/source, validate this
document's local source links and amended scope coverage, verify the shared
`plan.md` and canonical #166 file match merged master, run the documentation
contract and `git diff --check`, inspect staged files, then verify the pushed
commit, remote branch head, and master ancestry. These publication checks do not
claim the implementation gates below have passed.

During implementation, extend existing tests where they actually exercise the
changed behavior. Existing focused controls to run from the Duris worktree:

```sh
python3 tests/async/test_lich_death_experience.py
python3 tests/async/test_world_quest_xp_feedback.py
python3 tests/async/test_chaos_infinite_starting_grants.py
python3 tests/async/test_newbie_kit_plan.py
python3 tests/async/test_newbie_paladin_reward_contract.py
python3 tests/async/test_creation_availability_contract.py
python3 tests/async/test_creation_all_races_toggle.py
python3 tests/async/test_creation_all_classes_toggle.py
python3 tests/async/test_creation_prompt_journey.py
./scripts/format.sh --check
make -C src
make world
git diff --check
```

Add focused executable death/notification and creation/proc coverage plus
`tests/async/test_issue213_tutorial_parity.py` and
`tests/async/run_issue213_onboarding_journey.py` only for behavior not covered by
those controls. These are proposed tests, not existing passing checks. The
parity test must cover authored and generated output; the journey runner must
accept an explicit server path and backend, reuse existing disposable backend
support, and retain source/binary/world IDs and observed results under `bin/`.
Build the appropriate flat-file binary for that leg and use the existing
disposable MariaDB wrapper for the SQL leg. Existing source-text contracts
are controls, not substitutes for executing death, selection, or proc dispatch.

For the companion frontend, add component/connection tests for race/side
refresh, stale responses, menu selection, and invalidation. In its `frontend/`
directory run `pnpm type-check`, the focused tests via
`pnpm test:unit --run <test-paths>`, and `pnpm build`; then run the browser
journey against the disposable MUD. Record exact new test names/commands as
they are implemented. Do not use a mocked hometown list as full parity proof.

Completion requires all seven locked outcomes above, unchanged original
tutorial files and racial-hometown content, exhaustive eligibility/reference/
mechanical parity checks, the observed terminal/browser journeys, and
persisted XP/home recovery evidence. Recheck master before integration and
review the actual diff for unrelated work. No CI wait is a completion gate;
missing local/runtime/browser evidence remains explicitly incomplete.

## Delivery order and operational boundary

Use reviewable commits on the linked branch: death policy/warning; authored
copies plus remapping; compiled bindings and creation integration; focused
acceptance coverage/help. Land the companion DurisWeb change with coordinated
protocol compatibility. Do not leave exposed tutorial menu options pointing
at absent data/procedures between releases.

No SQL schema migration is anticipated: new content IDs and home values use
existing formats, and the warning needs no persistent state. Verify this
against the implementation diff rather than generating a speculative migration.
Ship matching server and generated world data; do not remove newly used room
IDs during rollback while characters still persist there. Any operational
rollback must first account for those characters using existing relocation
procedures and owner-authorized production handling.

Provisional effort: **16-28 active engineering hours** for content mapping,
server/client integration, and focused qualification, subject to the actual
NPC-race parity audit. This is not a fixed elapsed schedule or a production
acceptance claim. The publication of this plan leaves implementation, review,
gameplay qualification, and any deployment outstanding.
