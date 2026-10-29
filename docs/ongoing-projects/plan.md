# Issue #420: preserve Shambler capacity while defensive images are active

Status: **planning complete; implementation not started**. Updated 2026-10-30.
Issue: [Duris #420](https://github.com/LuminariMUD/Duris/issues/420).
Branch: [branch/issue-420-plan](https://github.com/LuminariMUD/Duris/tree/branch/issue-420-plan).
Source baseline: origin/master at b23ea8c65a467d17683ccd5de91f66b362209d06.
Worktree: /home/aiwithapex/projects/duris-issue-420.

The previous plan and completed qualification record for #428 are preserved
byte-for-byte in [plan-issue-428.md](plan-issue-428.md). This request authorizes
investigation, this plan, commit/push and issue linkage; implementation is
subsequent work.

## Outcome and proposed balance decision

At Shambler's admission boundary, exclude linked NPC images whose prototype is
IMAGE_REFLECTION_VNUM (250) from the ordinary-pet count. Zero or one ordinary
pet permits a cast, independent of whether zero, one, two, three or four images
exist. Two or more ordinary pets still reject it. Any existing linked shambling
mound still rejects another cast, including when it is the only ordinary pet.

This is the proposed resolution of the issue's open balance question, not a
claim that the code or existing help already establishes that rule. It is
specific to admission to Shambler. It does not make images cease to be pets.

**Shared-prototype consequence:** Reflection and Mirror Image both create
pet-linked NPC 250. The proposed rule intentionally exempts both at this one
boundary, including Reflection reached through its racial innate or an item.
A Reflection-only exception that still counts otherwise identical Mirror Image
pets would require a distinct policy and additional provenance; this plan does
not silently introduce that distinction.

Keep the explicit Titan-versus-Reflection exclusions, genuine pet caps, mound
uniqueness, image ownership, duration, replacement and combat behavior. Ordinary
Displacement remains an affect with no pet-capacity consequence.

## Source findings, checked independently of the issue

All paths and line numbers below refer to the baseline above.

1. **Reflection really creates pet links.**
   src/classes/sillusionist.c:573-704 checks for an existing Titan, replaces
   image followers, computes BOUNDED(1, (level - 26) / 5, 4), loads mobile 250,
   and calls setup_pet(image, ch, 3, PET_NOCASH). Effective levels 31/36/41/46
   produce 1/2/3/4 images. Images attach to the caster even when the visual
   target is another player; preserve that existing ownership rule.
   src/classes/necromancy.c:236-314 creates the LNK_PET through
   linked_affect_to_char(). count_pets() counts every such link.

2. **Shambler has two separate admission rules.**
   src/magic/blispells.c:666-742 first rejects an existing linked mobile 100,
   then rejects count_pets(ch) > 1. Its army-prevention comment supports keeping
   the ordinary-pet cap, but does not specify how images should count.
   Terrain then selects 1-2, 2-4 or 3-6 mounds; unsupported sectors reject the
   cast. The top comment's 1d4+2 is not the rule for every terrain.
   Success retains setup_pet(..., 15, PET_NOCASH | PET_NOAGGRO), death-event
   scheduling, following and TAG_CONJURED_PET.

3. **A global counting change would broaden the balance change.**
   Other actual consumers of count_pets() are bard charm in
   src/classes/bard.c:827, the pet shop in src/specs/specs.room.c:868, NPC
   corpse creation in src/mob/mobact.c:1118, and NPC Shambler selection at
   src/mob/mobact.c:10772. The last independently requires zero total pets
   before choosing the spell. Keep all four decisions and the generic counter
   unchanged. Direct Shambler execution uses the corrected admission rule for
   any caster; NPC autonomous spell selection remains its current separate rule.

4. **The existing image constant is precise enough; the illusion helper is not.**
   src/core/defines.h:1374 defines IMAGE_REFLECTION_VNUM.
   src/magic/magic.c:1727-1880 shows Mirror Image calling make_mirror(), which
   loads the same prototype and calls setup_pet().
   src/classes/innates.c:2470 also loads mobile 250 for Project Image, but does
   not create a pet link in that path, so it contributes nothing to either count.
   is_illusion_char() in src/classes/sillusionist.c:1400 also identifies
   illusion disguises. Reusing that broader predicate could exempt real pets
   merely because they are disguised; use the NPC/prototype check instead.

5. **The Reflection entry routes and both Titan exclusions already exist.**
   src/classes/innates.c:2647-2666 dispatches the racial innate to
   spell_reflection() after its own Titan check and cooldown handling.
   src/classes/sillusionist.c:1871-1920 rejects Titan creation while a
   mobile-250 image follower exists; Reflection independently rejects a linked
   Titan. Neither restriction should move into a pet-count helper.
   src/classes/skills.c:2217-2218 registers Shambler as an 11th-circle Scourge
   specialization spell. A real command journey must satisfy that eligibility,
   rather than assuming that any level-36 character can cast it.

6. **Displacement and help need careful interpretation.**
   src/classes/psionics.c:1461-1483 adds an AC affect without creating followers
   or links; the reported name does not establish a Displacement defect.
   lib/information/help_index contains the maintained Reflection and Shambler
   entries (around lines 13489 and 25410). Neither currently explains this
   image-counting rule. Add concise player wording there with the fix.

## Executable planning evidence

A temporary probe under bin/qualification/issue420/ reused the existing
Reflection ownership fixture and extracted the current, unmodified production
bodies of spell_reflection(), setup_pet(), count_pets() and spell_shambler().
It executed all 20 combinations of 0/1/2/3 ordinary pets and 0/1/2/3/4 actual
Reflection-created images under ASan/UBSan.

Observed results:

- With no ordinary pets, zero or one image reaches Shambler's mound loader;
  two, three or four images trigger the exact pet-cap rejection.
- With one ordinary pet, zero images reaches the loader; even one image rejects.
- With two or three ordinary pets, every image count rejects.
- The generic count equals ordinary pets plus images throughout.

The controlled mound loader intentionally returned null. This proves current
admission behavior, not successful summons, event expiry, command reachability,
or a booted-world reproduction. Room/link services and RNG were controlled.
The ignored result is bin/qualification/issue420/baseline.txt; the temporary
probe source and executable are removed after investigation. The implementation
regression below must exercise successful mound creation, not stop at this probe.

Existing baseline checks also passed:

- python3 tests/async/test_reflection_image_ownership.py: 409 casts plus Titan
  rejection under ASan/UBSan, preserving prototypes, ordinary pets, links, combat
  redirection and private-string cleanup. Extraction/room services are fixtures.
- python3 tests/async/test_innate_reflection.py: real innate dispatch,
  race/level eligibility, self targeting, configurable cooldown and Titan
  rejection. Its Reflection body is stubbed; it does not prove the combined
  innate-to-Shambler route.

## Non-goals

- No change to count_pets() or its other consumers, no generalized capacity
  policy, optional parameter, image-origin field, new configuration or service.
- No change to image links, charm, durations, strings, damage, replacement,
  Mirror Image creation rules, racial unlocks/cooldowns or Titan restrictions.
- No change to Shambler terrain yields, lifetime, ordinary-pet limit, existing
  mound exclusion, class access or NPC autonomous spell selection.
- No pet persistence migration, old-instance rewrite, production operation,
  deployment, full burn-in or dependency on hosted CI.
- Do not fold Conjurer capacity work #215, prior image-ownership work, or
  unrelated pet/lifetime investigations into this fix.

## Files and ablated implementation sequence

Expected production edit: src/magic/blispells.c only.
Expected proof/documentation edits: tests/async/test_reflection_image_ownership.py,
one focused command journey tests/async/test_shambler_reflection_journey.py
(new), lib/information/help_index, and this plan's completion record.
Retain test_innate_reflection.py as an unchanged compatibility test unless the
new regression exposes a necessary gap.

1. **Extend the existing native regression before changing the guard.**
   Add the production Shambler body and generic counter to the current Reflection
   fixture. Model mobile 100, successful materialization and observable
   scheduling/tagging at the existing controlled service boundaries. Assert
   returned mounds and unchanged image/ordinary-pet state, not just absence of
   refusal text. At least image-only 2+ and one ordinary pet plus one image must
   fail against the current source. Do not create a second harness framework.

2. **Count at the existing Shambler boundary.**
   In its existing linked-pet traversal, retain the mound rejection and tally
   only pets that are not NPCs of IMAGE_REFLECTION_VNUM. Use the resulting
   local count for the existing > 1 guard. Preserve rejection precedence and
   the terrain/summoning body. Add a short comment explaining this admission
   policy. No new production helper or header declaration is necessary.
   Keep all non-image pets counted; do not use flags such as PET_NOCASH,
   temporary duration, charm status, or the broad illusion predicate.

3. **Drive the real command route in disposable state.**
   Reuse test_flatfile_combat_journey.py and its server build/world/socket
   helpers. Follow the staff-controlled fixture setup demonstrated by
   run_racial_pulse_journey.py, but keep this scenario separate from its
   unrelated race-stat checks. Supply the image and mound prototypes and a
   supported outdoor room. Configure synthetic, otherwise eligible Scourge
   casters with known spell access, mana and preparation; do not change normal
   race/class rules. Exercise racial "innate reflection" for Gnome and Kobold,
   then "cast 'shambler'" while at least two images remain. Also cover the normal
   spell route to Reflection on a prepared test caster and a Mirror Image
   command control for the shared-prototype policy.
   Observe image and mound identities/counts plus ownership/following through
   existing inspection facilities. Synchronize on each command's response and
   following prompt; an unsolicited prompt alone cannot prove completion.
   Check a repeated Shambler rejection, ordinary-pet rejection and both
   Titan/Reflection orders. Recast/cleanup must leave ordinary pets intact.

4. **Document and finish proportional qualification.**
   Explain in Shambler help that Reflection/Mirror Image images do not consume
   its ordinary-pet allowance, that at most one other pet may precede the cast,
   and that an existing mound prevents another cast. Add a brief cross-reference
   in Reflection help without claiming a global exemption. Run the checks below,
   reread the entire diff and record exact results and limitations here.

Ablation keeps one local counting decision, the already available image constant,
an extension of existing native coverage, and one small journey using existing
helpers. A global counter change would alter four unrelated consumers. A broad
illusion predicate changes more than image counting. Per-spell provenance adds
state without serving the proposed shared-image rule. Removing image links
would disturb ownership and lifecycle. These alternatives are dropped.
The command journey stays because the existing tests do not execute the combined
player workflow. No alternative production implementations need to be built.

## Proof and acceptance

- Cross 0/1/2/3/4 images with 0/1/2/3 ordinary pets: casts succeed only with at
  most one ordinary pet and no existing mound. Include a non-image summoned pet
  as well as a charmed-pet control; both count. Non-pet links do not count.
- An existing mound rejects with zero or multiple images, including when that
  mound is the only ordinary pet. Additional casts cannot accumulate mound groups.
- In supported terrain, admitted casts create the unchanged yields (1-2, 2-4,
  3-6) under controlled RNG. Unsupported terrain still rejects without creating
  anything. New mounds retain pet links/followers, tagging and scheduled lifetime.
- Image-only and mixed cases leave image identity, strings, links and existing
  ordinary pets intact. Reflection replacement removes only the previous images;
  after image cleanup the ordinary-pet decision is the same.
- The generic count_pets() still counts images. This demonstrates that the
  shared helper's contract, including its other callers, has not changed.
- Real Reflection spell and racial routes reach successful Shambler creation;
  the Mirror Image control follows the explicitly proposed rule. Existing
  Displacement alone adds no pet restriction.
- Titan first still blocks Reflection; images first still block Titan.
  The racial rejection does not spend cooldown or add combat lag.
- Native and socket results are reported separately. A missing command journey
  leaves that acceptance item unverified; green helper tests cannot replace it.

Planned commands after implementation, with artifacts confined to bin/:

    python3 tests/async/test_reflection_image_ownership.py
    python3 tests/async/test_innate_reflection.py
    make -C src
    python3 tests/async/test_shambler_reflection_journey.py
    ./scripts/format.sh --check
    python3 tests/async/test_documentation_contract.py
    git diff --check

The proposed journey should build its fresh flat-file executable through the
existing helper by default, with an optional explicit freshly built binary as
the nearby journeys support. Confirm local/dev configuration before runtime
work; use private temporary accounts/world data, never live player state.
No persistence behavior changes, so restart/database qualification is not a new
gate. Production/full-world acceptance is outside this implementation estimate.

## Tracking and estimate

GitHub #420 is the work item for this branch. Searches for open PRs referencing
420 or Shambler/Reflection found none. Targeted max757/duris GitLab searches
found no matching Shambler work item; the Reflection result was unrelated
lifetime-qualification item #27. Do not link that item or close related historical
issues merely because they mention images or pets. Link this branch directly
in #420's Development section and provide the committed plan link there.
A planning-only commit must not use an issue-closing keyword.

Estimate: **2-3 hours of my active implementation time** for the documented rule,
including regression-first work, the small production change, help, the real
command journey, required build and reviewable commits. Approximately 30-45
minutes is native regression plus fix, 60-90 minutes is command-fixture setup and
runtime checks, and 30-45 minutes is documentation, build and final review.
Allow up to 4 hours if spell preparation or minimal-world fixtures require more
setup. This excludes a changed balance decision, external review, merge waiting
and deployment.

## Planning completion checks

Only this plan and preservation of the previous plan are committed. No
production C/C++ edit, full server build or booted-world reproduction is claimed
at this planning stage. The focused baseline evidence is recorded above.
Planning validation completed:

- python3 tests/async/test_documentation_contract.py: all 14 tests passed.
- git diff --check: passed.
- The archived #428 plan and baseline plan have identical SHA-256:
  db2e06ff1afe39dba4629cc840c579b994e04965df0e31995174625eee95fdbf.
- Only the requested plan and the intact historical archive are tracked changes;
  the original checkout's branch and files are preserved.
