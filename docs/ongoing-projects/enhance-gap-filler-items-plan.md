# Enhancement gap fillers: "The Halfway Works"

Status: complete and ready for review in [PR #998](https://github.com/LuminariMUD/Duris/pull/998).
All implementation and local qualification steps passed. No deployment.
Date: 2026-11-10.
Branch: `branch/enhance-gap-fillers`, stacked on
[PR #995](https://github.com/LuminariMUD/Duris/pull/995) (`branch/enhance-level-ceiling`),
which is stacked on the iVal stack tip
([PR #989](https://github.com/LuminariMUD/Duris/pull/989)).
Related: [PR #990](https://github.com/LuminariMUD/Duris/pull/990) (superseded by #995).

## Outcome and scope

PR #995 limits one replacement enhancement to a gain of 1 to 4 item value. That
leaves 54 pool items below item value 99 with no next step on current master, because their wear
slot has nothing 1 to 4 above them. On master those items could only advance
through a lucky jump of 5 to 8.

This implementation adds 33 new object templates, one per gap, so every one of
the 54 has a next step again. The templates exist only as enhancement results: they are
not placed in any room, on any mob, in any shop or in any quest.

Out of scope:

- The 23 other dead ends below 99 that are stuck on master today as well (the
  slot simply ends there), and the 74 dead ends from 99 to 168. Those were not
  lost by #995.
- Any change to enhancement code. If the gaps should instead be bridged in
  code (nearest higher item within the old reach when nothing is within +4),
  this plan is not needed at all. That alternative is a few lines in #995.

## Verified baseline

Re-measured during review on 2026-11-10 against master through #997. Native
world loading and the same binary/configuration produce 9,085 index entries
before the new records and 9,118 afterward, across 19,334 and 19,367 templates.
The baseline world is regenerated from the integrated world with only vnums
91534–91566 removed; it does not reuse the older implementation snapshot.

- 54 sources below item value 99 have a +5..8 candidate at or below 99 but
  no +1..4 candidate in any usable slot before this content.
- The 33 exact planned values restore a +1..4 path for all 54. Every filler
  also has an existing, non-filler +1..4 successor in its own slot.
- All original template scores, wear flags, index membership and reward-filter
  results remain identical between this fresh before/after pair.
- The original 53-source snapshot excluded #120015, a pair of gnomish
  eyeglasses. Master's flag correction makes it eligible; #91536 covers its
  additional 68 → 72 step. #44824 also enters the index, producing the other
  entry of baseline drift. The original snapshot is retained as history below.
- World vnums remain unique and ascending. No zone reset, shop or quest
  references the new vnums.
- Both native reward filters reject all 33 `_noquest_` records. The accepted
  Chaos-kit admission and material-rarity-report behavior remain unchanged.

## Review qualification (2026-11-10)

Current scratch evidence is under `bin/qualification/gap-fillers/` in the review
worktree: `review-baseline/index.csv`, `fillers/index.csv` and
`review-qualification.json`. `review-qualify.py` checks every exact target,
normalized slot, current lost source, original row and existing successor.
The isolated baseline and current world use the same native measurement binary.
These runners and generated files remain uncommitted, as required by this plan.

The server build, focused record and native enhancement tests, and native
constructor/template/offline-CLI parity over all 19,367 templates pass.
The real level-56 MariaDB journey passes 10 → 14 → 17 enhancement, exact
source/donor UID consumption and the 2,000-copper debit, then preserves the real
successor through server restart/reconnect. Each of four live boots matches all
9,118 measured index entries. Evidence: `journey.json` (`complete: true`).

## Decisions

1. **Theme: the Halfway Works.** The refusal message already speaks of "the
   item gods". Each filler is one of their unfinished pieces: the stranded item
   caught halfway through being reworked into the next real item in its slot.
   Names and descriptions blend the two neighbours, so the upgrade path reads
   as a story (a copper nose ring, then the same ring washed in silver, then
   the silver hoop). No shared prefix or set name; the family resemblance is in
   the descriptions.
2. **No placement.** No zone resets, shops, quests or loot tables. Every
   keyword list carries `_noquest_` so faerie bags and world quests skip them.
3. **One home.** All 33 go at the end of `areas/obj/wutvr.obj`, vnums 91534 to
   91566. That file currently ends at 91533, the next object in the world is in
   `undermountain.obj` at 92000, and zone 915 owns the range. The block keeps
   the ascending order and stays inside the enhancement index range.
4. **One slot each.** Wear flags are `ITEM_TAKE` plus the single target slot
   (guild insignia: `ITEM_TAKE | ITEM_GUILD_INSIGNIA`, as existing insignia).
   Multi-slot fillers would let enhancement drift between slots.
5. **Exact values.** Each template's item value must equal the target below
   under the stack's valuation. Stats are plain applies (hit points, a
   primary stat, saves, armor class for shields and worn armor) chosen to fit
   the two neighbours and tuned until the value matches. No affect bits, no
   procs, no spell effects, so nothing can trip the enhancement ban list.
6. **Guild insignia are generic.** The six insignia fillers are guildless
   badges in the same style as the existing ones in the pool (a king's tag, a
   hammer and anvil); they carry no guild binding.

## The 33 items

"From" is the stranded item or items; "to" is the next real item in the slot.
Values are item values under the stack.

| Vnum | Slot | Value | Name | From (value) | To (value) |
| ---: | --- | ---: | --- | --- | --- |
| 91534 | arms | 55 | a pair of squire's sleeves stitched for a knighting | tharnadian sleeves (51) | an armband of knighthood (56) |
| 91535 | earring | 97 | a blackened stud set with a sapphire chip | a spiked blackened earring (93) | a black sapphire earring (98) |
| 91536 | eyes | 72 | a jeweled eyepatch stitched from shed python skin | eyes of the zombie lord, a jeweled eyepatch of Boyard, gnomish eyeglasses #120015 (68) | a writhing python eye (74) |
| 91537 | eyes | 78 | a black knight's monocle of smoked glass | a writhing python eye, an eyepatch of Dagon, a black knight's visor (74) | the eyepiece of Kohlinar (79) |
| 91538 | eyes | 94 | a slit-pupiled lens of black glass | a lizard's eye (90) | the black eyepiece of Menzellon (95) |
| 91539 | face | 69 | a diver's half-mask of lacquered reed | a mask of Xlorkortor (65) | a crude snorkel pipe (70) |
| 91540 | feet | 88 | a pair of orog-hide boots dyed an unwise crimson | bone-reinforced boots of diorite, orog-hide moccasins (84) | a garish pair of shoes (90) |
| 91541 | horn | 5 | a pair of dented tin horn caps | the eviscerator (1) | a set of iron horns (7) |
| 91542 | horn | 70 | a chrome horn ring chipped with nightstone | a horn ring, a chrome horn (66) | a jagged nightstone ring (71) |
| 91543 | horn | 95 | a devil's horn sheath of fingerbone and hide | horns of a bantu devil studded with fingers (91) | leather-tipped horns (97) |
| 91544 | horse body | 19 | a rune-etched saddle with a mended girth | a leather saddle etched with runes (15) | a sturdy saddle (21) |
| 91545 | horse body | 58 | a woven saddle blanket trimmed with gold studs | a finely woven minotaur or centaur blanket (54) | a gold studded horse saddle (59) |
| 91546 | horse body | 67 | a hardened saddle of clouded glass-leather | a hardened leather saddle (63) | a transparent saddle (68) |
| 91547 | insignia | 22 | a king's tag carved with a coiled serpent | the kings tag, a symbol of Malch'hor Ganl (18) | a marble snake (24) |
| 91548 | insignia | 39 | a royal field-surgeon's badge | a royal badge of Arcium (35) | an emblem of healing (43) |
| 91549 | insignia | 52 | a guildmaster's seal of hammer and scale | a hammer and anvil, a scale and balance (48) | the atlantan badge of strength (53) |
| 91550 | insignia | 61 | a diamond-dust sigil that glows faintly blue | a small diamond tattoo (57) | a glowing blue crystal (64) |
| 91551 | insignia | 83 | a Shanatar signet furred with glowing moss | a clump of glowing fuzz, an emblem of Shanatar royalty (79) | the glowing pendant of Torg (84) |
| 91552 | insignia | 88 | a six-sided pendant of trapped glow | the glowing pendant of Torg (84) | an ethereal hexagon of life-force (89) |
| 91553 | nose | 14 | a copper nose ring washed in silver | a heavy copper nose ring (10) | a silver hoop nose ring (17) |
| 91554 | nose | 25 | a durethium nose stud shaped like a nautilus shell | a durethium nose ring (21) | a nautalis hairpin (26) |
| 91555 | quiver | 16 | a woodsman's quiver patched with a single dragon scale | a woodsman's quiver, a used denin instrument sack (12) | a faded dragonscale quiver (17) |
| 91556 | quiver | 21 | a fringed quiver strung with a bard's chime | eight quivers at 17, among them a faded dragonscale quiver and a fringed quiver | a glowing bard sack (23) |
| 91557 | quiver | 56 | a marble-capped quiver on a lifting strap | a marble quiver (52) | a leather lifting harness (59) |
| 91558 | quiver | 67 | a bloodstained quiver branded with a vile sigil | a quiver smeared with blood, a glowing stone (63) | a sigil of vile corruption (68) |
| 91559 | shield | 30 | a gale-scoured shield faced with a shed dragon scale | the blackened shield of the gale (26) | a shadow dragon scale (31) |
| 91560 | shield | 42 | a lashed shield wrapped in lizard hide | a lashed shield (38) | a lizardhide shield (44) |
| 91561 | shield | 71 | a storm-crested shield studded with raxian spikes | a granite shield with the storm crest (67) | a spiked raxian shield (72) |
| 91562 | tail | 17 | a bone tail ring bound in rawhide | a human bone tail ring (13) | a braided rawhide tail ring (20) |
| 91563 | tail | 38 | a tail guard tied with a blue ribbon | a protective tail piece (34) | a blue ribbon laced with silver thread (41) |
| 91564 | tail | 57 | a mithral tail ring set in sandstone | a woven mithral tail ring (53) | a ring of sandstone (60) |
| 91565 | tail | 77 | a war ribbon knotted through a snakeskin band | a blood soaked war ribbon (73) | a ring made of snake skin (79) |
| 91566 | tail | 97 | a Karthian tail spike capped in dragon scale | a Karthian tail spike (93) | a severed dragon tail (98) |

Each record has a room description and one extra description in the
house colour style. The shared motif for the extra description is a piece
visibly abandoned mid-work: one half finished in the manner of the "from" item,
the other in the manner of the "to" item.

## Record rules

For every new record in `areas/obj/wutvr.obj`:

- Keywords include the plain nouns of the name and `_noquest_`.
- Type follows the "from" item: `ITEM_ARMOR` or `ITEM_WORN` for worn pieces,
  `ITEM_SHIELD` for shields, `ITEM_QUIVER` for quivers (copy capacity values
  from the "from" quiver).
- Extra flags: none of `ITEM_ARTIFACT`, `ITEM_NOSELL`, `ITEM_NORENT`,
  `ITEM_NOSHOW`, `ITEM_TRANSIENT`; not `ITEM2_QUESTITEM`. Any of these would
  drop the template from the enhancement pool.
- All affect bitvectors zero.
- Material, weight and size copied from the "from" item.
- At most two `A` apply lines unless the target value cannot be reached with
  two.

## Original implementation handoff (2026-11-10, before review integration)

- Worktree: `/home/aiwithapex/projects/duris-worktrees/enhance-level-ceiling`;
  clean starting HEAD `8b0de0b85`. The primary checkout has unrelated dirty docs.
- Outcome: all 53 lost paths restored by 33 content-only templates. Non-goals
  remain the existing dead ends and enhancement-code changes.
- Files: `areas/obj/wutvr.obj`, one focused record test, and this plan.
- Proof: native index/value/reward filters, whole-world constructor/report parity,
  enhancement runtime test, world assembly/order, build, and local MariaDB journey.
- Ablation: reuse `_noquest_` and existing test/boot tools; no new consumer filters,
  valuation overrides, shared item framework, or reward/placement changes.
- Re-measured this branch with native world loaders: 9,083 index entries. All
  33 planned targets still bridge their slots. The old comparison must constrain
  candidates to value <=99, in addition to the +8 reach; otherwise five old
  dead ends are incorrectly counted as lost paths. Scratch measurements live in
  `bin/qualification/gap-fillers/` and are deliberately uncommitted.
  `measure.py fillers` assembles the current world and runs native index/value/
  reward filters; `analyze.py` reconstructs the original 53 sources from the
  preserved `baseline/` files. Do not overwrite that baseline with the new
  content; recreating it requires the starting revision `8b0de0b85`.
  `qualification.json`, `tuning.txt`, and `live-index.csv` hold the local results.
- All 33 records now have colored names, room and unfinished-work extra
  descriptions, the exact planned values, and two plain applies. Source
  material/size/weight are preserved; quiver capacity fields are copied from
  actual source quivers. Shields use the dedicated shield type. The fringed
  quiver uses HP and a small armor apply to reach 21 with two applies.
- Native qualification passed: 19,367 assembled templates; 9,116 index entries
  (+33); all 53 formerly lost paths restored; all 33 fillers have a real +1..4
  successor; zero fillers admitted by either reward filter. Original template
  scores/flags are unchanged. Assembled world vnums remain unique and ascending.
- Passed: `python3 tests/async/test_enhance_gap_fillers.py`,
  `python3 tests/async/test_enhance_ival_runtime.py` (ASan/UBSan),
  `python3 tests/async/test_item_value_template_runtime.py` (19,367 native
  constructor/template/CLI comparisons), `make -C src`, `make -C src all -j6`,
  and `git diff --check`.
- `areas/m_slow` also passed in the isolated qualification world, including
  lookup tables; generated files are not committed.
- Real server/MariaDB journey passed with a level-56 disposable test character:
  `enhance copper hoop` turns #37760 (10) into #91553 (14), then
  `enhance washed hoop` turns it into #9226 (17). Both original donor UIDs and
  the source UID are gone, the two fees debit exactly 2,000 copper, and the real
  successor survives a server restart and reconnect. Every live boot dumped
  the index under GDB and matched all 9,116 measured entries exactly.
- Exact local command:
  `tests/async/with_disposable_mariadb.sh python3 bin/qualification/gap-fillers/journey.py`.
  The scratch runner reuses the existing creation/SQL/command helpers, uses a
  new loopback-only schema, and removes its server/runtime/schema on exit.
  Evidence: `bin/qualification/gap-fillers/journey.json` (`complete: true`).
- Content committed/pushed as `a2130de61`; PR #998 is open, labeled
  `enhancement`, and targets `branch/enhance-level-ceiling` (#995). Its automated
  review completed without findings on that content commit. The final follow-up
  commit only records qualification in this plan.
- Remaining implementation/qualification work: none. Review/merge #998 after
  #995 and its parent #989; do not merge the content before its +4-rule parent.
- No deployment or release tag is part of this content PR.

## Completed implementation steps

1. [x] **Re-measure on this branch.** Generate the world from this branch's area
   files, boot the branch build, dump the enhancement index and recompute the
   stranded set and filler targets. If any target in the table moved, update
   the table before writing records. Keep the dump script and its output out of
   the repository.
2. [x] **Write the 33 records** at the end of `areas/obj/wutvr.obj`, in vnum order.
3. [x] **Tune values.** For each record, adjust apply modifiers until the item
   value equals the target. The stack's template valuation
   (`itemvalue(const object_template &)`) gives the same number the index uses;
   the quickest loop is the in-game `stat` output on a local boot, or the
   offline scoring used by `tests/async/test_item_value_template_runtime.py`.
4. [x] **Regenerate the world** (`areas/m_slow`) and confirm the assembled object
   file is still strictly ascending.
5. [x] **Add a focused test** (see below).
6. [x] **Qualify** (see below), then open the PR against
   `branch/enhance-level-ceiling`.

## Test

One new script, `tests/async/test_enhance_gap_fillers.py`, reading
`areas/obj/wutvr.obj` directly:

- vnums 91534 to 91566 all exist, in ascending order;
- each has `_noquest_` in its keywords;
- each has exactly `ITEM_TAKE` plus its one slot bit;
- none carries a pool-excluding extra flag or any affect bit.

Item values are not asserted in this script: they depend on the valuation code
and on every other template, and are covered by the qualification run.

## Qualification

- `python3 tests/async/test_enhance_gap_fillers.py`
- `python3 tests/async/test_enhance_ival_runtime.py`
- `python3 tests/async/test_item_value_template_runtime.py` (parity over all
  world templates, which now include the 33)
- `make -C src`
- Boot locally, dump the index again and confirm: the index holds 33 more
  entries, each filler has its target value, and the "lost by the +4 limit"
  count is 0.
- One live check on the local server with the test character: enhance a
  stranded item (for example #37760, a heavy copper nose ring, value 10) with a
  valid donor and receive its filler (#91553), then enhance that and receive
  the next real item.
- Confirm no filler appears as a faerie bag or world-quest reward candidate
  (both skip `_noquest_`).

## Risks and open points

- **Values drift.** Any later rebalance of item values can move the gaps or the
  fillers. The re-measure in step 1 is repeatable; the fix is to retune apply
  modifiers. The code alternative noted under scope does not have this cost.
- **Other template consumers.** The Chaos "enhanceable" equipment profile and
  the generated Chaos kit catalog are built from the enhancement index, so the
  33 may appear in generated Chaos kits. The owner accepted this on
  2026-11-10; no exclusion is needed. The material rarity report will list
  them; that is expected.
- **Zone ownership.** The fillers will report zone 915 (Wutvr) as their origin.
  `[pool_exclude_zone]` in `lib/enhance.cfg` is empty today; excluding that zone
  later would remove the fillers from the pool.
- **Master's guild insignia rule.** Insignia sources require a donor at least
  equal to the source value. The fillers do not change that.
- **Order of landing.** This branch must merge after #995. If #995 changes its
  gain limit, the targets change with it.
