# Issue #213: evil onboarding implementation plan

Tracking: [Duris #213](https://github.com/LuminariMUD/Duris/issues/213).
Implementation branch: `branch/issue-213-evil-onboarding`.
Status: local implementation and acceptance complete; the server stack and
DurisWeb companion are pushed and ready for review. Full native and browser
journeys pass on both backends. Review/integration and any production release
remain outstanding; the issue stays open until the coordinated stack lands.
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

## Current handoff — October 24, 2026

Active worktree: `/home/aiwithapex/projects/duris-issue213-plan`, branch
`branch/issue-213-final-acceptance`. The primary checkout remains on unrelated
`branch/contain-learning-feedback`; its changes were preserved. The requested
branch was clean and equal to its remote before merging master
`7d3bd3b957196f3136dbca61c01f2cba7f7ac298` as `ae99be838`, without rewriting
history. A fresh fetch on October 24 still resolves master to that revision.
No release tags, force pushes, production operations or CI waits are needed.

### Review stack and dependencies

Every listed PR is pushed, open and ready for review. Do not release an exposed
menu without the matching data/procedures and website companion.

- [#314](https://github.com/LuminariMUD/Duris/pull/314),
  `branch/issue-213-evil-onboarding`, `f81f62ffa`: universal death-XP protection
  below the configured default 30, including Lich delevel; one bold uppercase
  warning per upward crossing; both maintained death-help sources.
- [#315](https://github.com/LuminariMUD/Duris/pull/315), stacked on #314,
  `branch/issue-213-creation-eligibility`, latest correction `864dbc033`:
  shared terminal/web eligibility and pre-allocation validation. Firbolg and
  good-side neutral choices are enabled without opening restricted races.
- [#320](https://github.com/LuminariMUD/Duris/pull/320), stacked on #315,
  `branch/issue-213-tutorial-copies`, `39455b39c`: authored ID/reference
  foundation. Eight shops append only in `areas/shp/end.shp`, preserving all
  durable load-order shop IDs. Never add `wutvr.shp` in AREA order.
- [#331](https://github.com/LuminariMUD/Duris/pull/331), stacked on #320,
  `branch/issue-213-tutorial-routing`, `dcdb151fa`: minimal evil reskin,
  mechanics parity, compiled bindings, creation/routing and kit integration.
  Includes independent #328/#335 below; merge those dependencies first.
- [#333](https://github.com/LuminariMUD/Duris/pull/333), stacked on #331,
  `branch/issue-213-onboarding-acceptance`, `9f5bdc9f4`: real browser acceptance
  runner; includes independent #332.
- [#342](https://github.com/LuminariMUD/Duris/pull/342), stacked on #333,
  `branch/issue-213-final-acceptance`, `c82b266d9`: native service/death/recovery
  runner and side-neutral creation-menu recommendation. Includes #338 through
  `3943f366f`; merge that independent repair first. The review tree exactly
  matched the integration branch retained at `677f038a7` before the final
  racial spell-factor correction was merged through the parent. The active worktree
  now uses this clean review branch; its full native matrix passes on both backends.
- [DurisWeb #91](https://github.com/LuminariMUD/DurisWeb/pull/91),
  `branch/issue-213-hometown-parity`, `de17db6` (frontend code `9eb92e3`):
  selected alignment, stale-response rejection, pending-step protection,
  selection invalidation, omitted-home compatibility and phone layout.
  Worktree: `/home/aiwithapex/projects/durisweb-issue213`. Its own plan contains
  unpublished release-news text; no website publication was performed.

Independent fixes discovered through the required journeys:

- [#319](https://github.com/LuminariMUD/Duris/pull/319), `15e314e43`: remove
  Ailvio's already-disabled reset for nonexistent bank object 6081. The copied
  reset deliberately omits it; working sign/locker/object 3097 remain intact.
  This source repair is separate so feature originals remain byte-identical.
- [#328](https://github.com/LuminariMUD/Duris/pull/328), `71a86963b`: marked
  training dummies must not dispatch inherited prototype-1255 quest callbacks
  that intercept unrelated map requests. Included in #331 as `6cd922ca3`.
- [#332](https://github.com/LuminariMUD/Duris/pull/332), `909891027`: skip only
  zero-loss resurrection refunds. Real protected death/resurrection previously
  fabricated one XP and logged a false memory warning. Nonzero refund rules
  remain intact. Included in #333 as `e31d5141f`.
- [#335](https://github.com/LuminariMUD/Duris/pull/335), `48671f8a8`: bind the
  fourth source spell-up callback to actual Druid teacher 29237 instead of
  classless wolf 29265. #331's `5082f1df8` includes it and binds copy 91437.
- [#338](https://github.com/LuminariMUD/Duris/pull/338), `1725417fb`,
  `branch/fix-flatfile-shop-initialization`: initialize missing flat-file shop
  catalog/custody baselines after stock reconciliation. Existing journal
  commits both domains atomically; existing stock/revisions stay intact and
  UID collisions are refused. Includes legacy disabled-product handling and
  restoration by actual keeper identity, allowing legitimate quest/tradeskill
  callbacks. Included here as `2bf4c937d`; merge before releasing the new shops.
  Its clean review branch has the exact tested tree of retained unpublished
  development commit `a019ca70e`; no development history was rewritten.
- [DurisWeb #92](https://github.com/LuminariMUD/DurisWeb/pull/92), `aeeab8a`:
  match server account names (3–14 letters/underscores) before connecting.
  This is independent of #91.

### Implementation facts needed to continue

- Chaos zone 912: Life entity IDs +68400, zone +684. Wutvr zone 914: Ailvio
  entity IDs +62200, zone +622. Exactly 124 rooms, 108 mobiles, 143 objects,
  32 quest-controller records and eight appended shops. Nine new authored
  files plus the existing append-only shop tail; generated outputs stay ignored.
  All ten original authored tutorial files remain unchanged on the feature.
- Home IDs append as Wutvr 25 and Chaos 26. Terminal keys C/W are distinct;
  good Thri-kreen retains P for Payang and uses L for Life. Complete existing
  class/racial entry tables and Tiefling's Arachdrathos default/departure are
  retained. Explicit tutorial selections bypass only that default override.
- One shared race/side/home predicate serves terminal count/display/selection
  and web list/submission. Supplied malformed, zero, negative, fractional,
  wrong-side or unavailable homes fail before allocation/save/kit grants.
  Omitted home uses existing racial defaults. Legacy race-only neutral lists
  return only racial choices; responses echo race/alignment for stale detection.
- Reuse the original guide/tag, signs, stream, search/map controllers, bandage
  pair, four caster families, eight shops, two pet shops, inns and departure.
  Direct Wutvr kit uses copied invitation 91519 instead of 29319; entering from
  stage one grants no second kit. World-quest deny zone 292 is mirrored for 914.
  Shared sign READ callbacks were corrected from duplicate LOOK branches.
- `tutorial_mobile_mechanics_race()` applies only to 70 exact copied VNUM/new
  race pairs. It retains original loaded stats/innates/resistances/equipment,
  giant classification and victim XP. Review exposed runtime visible-race
  checks that still altered combat. Commit `436b77652` also routes Minotaur
  berserk/hit procs, Orc horde damage/counting, Drow dodge, Barbarian cold,
  Gith word vulnerability and racial casting modifiers through that profile.
  Follow-up `dcdb151fa` also selects configured offensive/defensive racial
  spell-damage factors by this profile, with deliberately different factor
  controls in the production-predicate ASan/UBSan test. Both full builds pass.
  Player/unrelated-NPC controls remain unchanged. The P2 review thread on #331
  is resolved after executable sanitizer checks and both builds passed.
- Source maps are transient/no-rent: assert live map delivery and absence from
  durable ownership, without changing flags. The secret shop's authored route
  is `touch orb` / `enter mirror`; do not add directional links. Pet purchases
  use the advertised numbered list entry. Source zero-price/visibility rules
  may legitimately produce an empty shop list; do not invent stock/prices.

### Completed local qualification

Already passing evidence under ignored `bin/qualification/issue213/`:

- Both maintained full builds and world generation. Focused executable
  death/Lich/warning/XP, creation/hometown, 36,360 legacy kit selections,
  copied-procedure, world-quest policy and authored/generated parity controls.
  ASan/UBSan covers runtime racial combat/casting and the independent dummy,
  zero-loss refund, shop repository/bootstrap/custody/runtime repairs.
- `run_issue213_tutorial_profiles.py`: all 108 real loaded source/copy NPCs
  with two identical RNG seeds, **216 comparisons and zero differences per
  backend**. This proves loaded profiles, not runtime racial dispatch; the
  separate real combat-block/casting tests cover the review finding above.
- `run_issue213_browser_journey.py`: real Chromium on flat-file and MariaDB.
  Firbolg/neutral choice refresh, stale selections/back navigation, 390px
  layout, four forged submissions allocating no player, evil Thri-kreen
  Chaos → Wutvr → racial departure, all three saved home fields and actual
  uppercase warning at computed font weight 700. Only unrelated HTTP shell/map
  endpoints were fixtures; all MUD/creation traffic used the full real world.
  The inherited Vue Router `next()` deprecation remains nonblocking.
- `run_shop_bootstrap_journey.py`: real fresh full-world flat-file shop
  initialization and cold restore with byte-identical catalog; real Wutvr
  purchases on both backends deliver/persist a bandage and charge one copper.
- Full native Ogre and Firbolg journeys on both backends completed search/potion,
  bandaging, three-item quest payout, all eight shop bindings and purchase,
  both pets, all four caster families, rent/relogin, reset, racial departure,
  protected death/resurrection at 1/29, bold crossing, level-30 loss and cold
  XP/home recovery. The runner checks each family's first authored buff,
  respecting finite NPC slots and original spell power/timing. Staff allocates
  the three body-part quest prerequisites; real GIVE dispatch and reward effects
  are observed. Encounter parity is separately covered by loaded profiles and
  production combat/casting regressions, rather than a live balance study.

The **full unfiltered native runs pass on both backends**:
`onboarding-{flatfile,mariadb}-final.json` / `*-run.log`, with `completed: true`,
seven routes, four direct starts and **28 acceptance records per backend**.
Both observed Ogre/Firbolg deaths at level 29 preserved 12,345 XP through
resurrection; at level 30 normal loss delevelled them to 29. Final cold restart
preserved those exact XP/level values and all three racial-home fields.
The frozen runner hash is
`7ec5a3d64ec20ab3d324d850df80008d676e4cd0ea639119913e6bb40fd2c77c`.
It covers Ogre/Firbolg full services/death plus Goblin Sorcerer,
evil Thri-kreen/Minotaur/Tiefling and Human routes; direct Faang/Ugta/Wutvr/Ailvio
starts; repeat rewards and mid/final cold restarts. Raw ANSI and clean client
transcripts are saved with the JSON filename prefix. Evidence records source,
runner, world and binary hashes. Fixed evil races use their authoritative evil
racewar side regardless of moral alignment; neutral cases explicitly choose E.

The last racial spell-factor selector correction was built to separate
`bin/server/dms_racial_final` and `dms_flatfile_racial_final` paths, preserving
the matrix's original binary hashes across its cold restarts. The
checked-in configuration has no non-unit racial spell-damage factors, so that
selector change preserves the matrix's observed behavior. Reuse that journey
evidence alongside the new non-unit-factor executable regression and both
incremental full-build logs (`build-racial-factors-{backend}.log`); do not rerun
the entire matrix for a selector that is numerically neutral in that fixture.
The canonical `dms_new`/`dms_flatfile` binaries were relinked afterward; both
final full-build logs are `build-final-{backend}.log`.

Commands from this worktree (the matching binaries already exist):

```sh
python3 tests/async/run_issue213_onboarding_journey.py --server bin/server/dms_flatfile --backend flatfile --output bin/qualification/issue213/onboarding-flatfile-final.json
tests/async/with_disposable_mariadb.sh python3 tests/async/run_issue213_onboarding_journey.py --server bin/server/dms_new --backend mariadb --output bin/qualification/issue213/onboarding-mariadb-final.json
python3 tests/async/test_issue213_tutorial_combat.py
python3 tests/async/test_spellcast_racial_multiplier.py
```

For browser reruns supply `--frontend-url http://127.0.0.1:15173`,
`--frontend-source /home/aiwithapex/projects/durisweb-issue213` and
`--browser-executable /home/aiwithapex/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome`
to `run_issue213_browser_journey.py`, with matching server/backend/output; wrap
the MariaDB leg as above. Recreate the loopback frontend first; the task-owned
Vite listener on 15173 was stopped after qualification.
Browser plugin was unavailable, so regular Playwright was used.

The full diff's format check, 14 documentation checks, original-file equality,
authored/generated parity and world-quest controls pass. A final master fetch
still resolves to `7d3bd3b95`. Task-created obsolete authoring/debug scripts and
the superseded plan backup were removed; qualification evidence remains ignored.
Recovery stash `875ba9317` has already been restored; **do not apply it again**.
Primary unrelated work and unmerged review branches/worktrees remain preserved.
No schema migration is needed.

Next: review and integrate the listed independent fixes, then the feature stack
in dependency order, coordinating DurisWeb #91 with authoritative validation.
No implementation or required local qualification remains open. Keep #213 open
through review/integration. Any deployment, live-player acceptance or production
help publication needs its own authorized operational work. Reuse valid local
proof unless a reviewed change affects its path; no full burn-in or CI wait is
a gate for this completed implementation request.


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
production configuration. The October 19 planning inventory used no live server,
loaded world or gameplay journey; implementation qualification is recorded above.

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
`areas/{wld,mob,obj,qst,zon}/wutvr.*`, eight appended records in
`areas/shp/end.shp`, plus `areas/AREA`. Shops must append there to preserve
the existing durable load-order shop IDs; do not add a wutvr.shp in AREA order.
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
those controls. These tests are now implemented and passing as recorded above. The
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

Content mapping, server/client implementation and required local qualification
are complete. The current handoff records observed proof and the review-ready
stack. Review, coordinated integration and any separately authorized production
release remain; no production acceptance is implied.
