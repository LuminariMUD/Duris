# Issues moved to Discussions: content backup

Status: incomplete, stopped 2026-09-23. This document holds the full original
text of the 30 issues that were closed on GitHub during a move to Discussions.
The move stopped partway when GitHub suspended the account that ran it,
`moshehbenavraham`. The discussions it created belong to that account and
can't be relied on while the suspension lasts.

## What happened

On 2026-09-23 a script started moving every open issue that wasn't a definite
bug into Discussions. For each issue it created a discussion from the issue's
text and labels, re-posted the issue's comments as replies, and closed the issue
as *not planned* with a comment pointing to the discussion. After 30 issues,
GitHub suspended the account. The script had made about 100 posts in 7 minutes.

- **Closed issues:** the issues were closed, not deleted. The original issue
  text and comments stay on GitHub. A maintainer with triage access can reopen
  them to put them back in the tracker. Anything written by `moshehbenavraham`,
  including the bodies of #63 and #616 and every "Moved to discussion" closing
  comment, may be hidden while the account is suspended.
- **Discussions:** #627–#656 were created by the suspended account. On
  2026-09-23, GitHub's public API still returned them with their full text, but
  they may be hidden or removed. The text below comes from the GitHub API
  immediately before the move, so it doesn't depend on them.
- **Partial move:** the discussion for #487 was created as #657, without
  labels, but issue #487 is still open. #657 is a stray copy.
- **Not started (13):** #126, #127, #146, #253, #258, #278, #299, #329, #453,
  #466, #488, #489 and #490 are still open issues.
- **Kept as bugs (12):** #373, #516, #525, #545, #551, #558, #568, #590, #621,
  #622, #623 and #624 were never meant to move.

To undo the move, reopen the 30 issues below. The matching discussions can
be deleted by a maintainer or kept.

## Closed issues

| Issue | Title | Author | Discussion | Category | Comments |
| --- | --- | --- | --- | --- | --- |
| [#63](#issue-63) | Upstream Origin Issues Audit (xanadinn/DurisMUD) | moshehbenavraham | #628 | General | 3 |
| [#474](#issue-474) | Economy accounting: implement balanced coin transfers and auditable item custody | xander-l | #644 | Ideas | 18 |
| [#475](#issue-475) | Economy accounting [01/16]: define conservation contracts and inventory every economic writer | xander-l | #645 | Ideas | 4 |
| [#476](#issue-476) | Economy accounting [02/16]: implement bounded balanced plans and versioned operation links | xander-l | #646 | Ideas | 3 |
| [#477](#issue-477) | Economy accounting [03/16]: add atomic SQL journal storage and immutable migrations | xander-l | #647 | Ideas | 6 |
| [#478](#issue-478) | Economy accounting [04/16]: persist accounting evidence atomically in flat-file mode | xander-l | #648 | Ideas | 9 |
| [#479](#issue-479) | Economy accounting [05/16]: establish opening balances and a restart-safe cutover | xander-l | #649 | Ideas | 10 |
| [#480](#issue-480) | Economy accounting [06/16]: journal wallet, bank and physical coin transfers | xander-l | #650 | Ideas | 1 |
| [#481](#issue-481) | Economy accounting [07/16]: account for coin issuance, expenses and authorized adjustments | xander-l | #651 | Ideas | 0 |
| [#482](#issue-482) | Economy accounting [08/16]: link item custody and lifecycle events to economic operations | xander-l | #652 | Ideas | 1 |
| [#483](#issue-483) | Economy accounting [09/16]: make shop purchases and sales balanced atomic exchanges | xander-l | #653 | Ideas | 0 |
| [#484](#issue-484) | Economy accounting [10/16]: journal collector purchases, buybacks and item expiry | xander-l | #654 | Ideas | 0 |
| [#485](#issue-485) | Economy accounting [11/16]: account for auction escrow, claims, refunds and settlement | xander-l | #655 | Ideas | 1 |
| [#486](#issue-486) | Economy accounting [12/16]: preserve accounting through death, world lifecycle and recovery | xander-l | #656 | Ideas | 0 |
| [#505](#issue-505) | Investigate 889 main-production coin-transfer ESTALE failures (2026-09-18) | xander-l | #643 | General | 0 |
| [#509](#issue-509) | Performance: cache mundane-event handles for world-activity wakeups | xander-l | #642 | Ideas | 1 |
| [#510](#issue-510) | Performance: remove transient allocations from PC-corpse activity traversal | xander-l | #641 | Ideas | 1 |
| [#526](#issue-526) | Add guarded exact-UID recovery for active custody with missing player payloads | xander-l | #640 | Ideas | 0 |
| [#533](#issue-533) | Do not block authenticated player login on non-core persistence failures | xander-l | #639 | Ideas | 1 |
| [#539](#issue-539) | Improve quantity-buy syntax, shop listings, and purchase feedback | xander-l | #638 | Ideas | 1 |
| [#546](#issue-546) | Investigate elemental aura no-op reports on Fire and Air Plane | xander-l | #637 | Q&A | 1 |
| [#561](#issue-561) | Telemetry: validate the live repository/schema contract before enabling the writer | xander-l | #636 | Ideas | 0 |
| [#564](#issue-564) | CI: run telemetry migrations and SQL repository round trips for every record kind | xander-l | #635 | Ideas | 0 |
| [#565](#issue-565) | Telemetry: define repository mappings and schema checks from one canonical column contract | xander-l | #634 | Ideas | 0 |
| [#566](#issue-566) | Telemetry: preserve or explicitly account for queued records across restart and copyover | xander-l | #627 | Ideas | 0 |
| [#567](#issue-567) | Data quality: register and reconcile the telemetry outage beginning 2026-09-21 00:49:26 UTC | xander-l | #633 | General | 0 |
| [#569](#issue-569) | Persistence: audit, repair, and prevent player item topology rows with missing payloads | xander-l | #632 | General | 4 |
| [#570](#issue-570) | Persistence: correlate corpse rejection and critical-command integrity recovery to a terminal custody outcome | xander-l | #631 | General | 3 |
| [#598](#issue-598) | Add player-facing feedback for bartender kill-quest XP | xander-l | #630 | Ideas | 0 |
| [#616](#issue-616) | Flight Dragon network: learnable destinations, distance-priced tickets and discovery EXP (mobs 47015–47041) | moshehbenavraham | #629 | Ideas | 2 |

## Original text

Each body and comment is reproduced exactly inside a fenced block, except that
Windows line endings were converted to Unix ones.

<a id="issue-63"></a>

### #63: Upstream Origin Issues Audit (xanadinn/DurisMUD)

- Issue: https://github.com/Community-Duris/Duris/issues/63
- Opened by `moshehbenavraham` on 2026-08-31
- Labels: `documentation`, `enhancement`, `help wanted`
- Discussion created: #628 (General)

````markdown
A technical audit of all 8 issues (only 5 remain) filed in upstream repository [`https://github.com/xanadinn/DurisMUD/issues`](https://github.com/xanadinn/DurisMUD/issues), evaluated against the current state of the Duris codebase.

---

## Executive Summary Matrix

| # | Upstream Issue Title | Upstream State | Current Codebase Status | Category |
|---|---|:---:|:---:|---|
| **#1** | [DEFINITIONS (Read First) OPIs/balance/zone issues and suggested solutions](https://github.com/xanadinn/DurisMUD/issues/1) | `OPEN` | **OUTSTANDING** | Content / Item Balance Design Proposals |
| **#3** | [Hellfire vs. Paladin](https://github.com/xanadinn/DurisMUD/issues/3) | `OPEN` | **OUTSTANDING** | Combat & Spell Mechanics Balance |
| **#4** | [Minotaur Balance](https://github.com/xanadinn/DurisMUD/issues/4) | `OPEN` | **OUTSTANDING** | Racial Stat / Innate Balance |
| **#5** | [3rd Racewar Side Re-Enabling](https://github.com/xanadinn/DurisMUD/issues/5) | `OPEN` | **OUTSTANDING** | Game Architecture / Feature Request |
| **#6** | [single hand 2 hand weapons (race/class)](https://github.com/xanadinn/DurisMUD/issues/6) | `OPEN` | **OUTSTANDING** | Equipment / Combat Mechanics Request |


---

## Detailed Findings per Issue

### Issue #1: OPIs / Balance / Zone Issues & Suggested Solutions
- **Upstream URL**: https://github.com/xanadinn/DurisMUD/issues/1
- **Status in Current Codebase**: **OUTSTANDING (Unimplemented Proposals)**
- **Technical Analysis**:
  This issue contains long-form balance proposals targeting three specific items and general mechanics:
  1. **`the mace of mentality` (`VNUM 44188`)**:
     - *Mechanism*: Procs `spell_reflection(50)` on a 5-minute timer via `CMD_SAY "mentality"` (`src/specs.object.c:14231`).
     - *Spawn Location*: Still configured as a quest reward in Tikitzopl (`areas/qst/tikitt.qst:255`).
     - *Proposal*: Convert to a Winterhaven Quest Item (WHQI). Currently unchanged.
  2. **`a metal flask marked 'word of recall'` / `a scroll of word of recall`**:
     - *Mechanism*: Portable `spell_word_of_recall` (`src/magic.c:8288`) items in shops and high-level zones (CRL / Shanat Citadel).
     - *Proposal*: Exponentially increase cost (e.g. 1M platinum) or gate behind long questlines. Currently unchanged.
  3. **`the bracer of the whirlwinds` (`VNUM 76032`)**:
     - *Mechanism*: Procs `AFF2_FLURRY` upon tapping/invoking (`src/specs.object.c:11185`).
     - *Spawn Location*: Loaded in Tempest Court / Cosmic zone (`areas/obj/cosmic.obj:411`, `areas/qst/cosmic.qst:61`).
     - *Proposal*: Move to Celestia and allow in Celestia Bartender Quests. Currently unchanged.

---

### Issue #3: Hellfire vs. Paladin
- **Upstream URL**: https://github.com/xanadinn/DurisMUD/issues/3
- **Status in Current Codebase**: **OUTSTANDING (Configurable via Properties)**
- **Technical Analysis**:
  - *Request*: *"Rebalance hellfire vs paladin heal proc"*.
  - *Mechanics*:
    - Spell Absorption: `src/fight.c:4441-4450` absorbs spell damage and heals the `AFF4_HELLFIRE` victim based on `get_property("vamping.hellfire.absorb", 0.14)`.
    - Physical Damage Vamping: `src/fight.c:5469` vamps damage dealt by `PHSDAM_HELLFIRE` based on `get_property("vamping.hellfire", 0.14)`.
  - No explicit balance patch was committed specifically changing Paladin holy weapon heal procs against Hellfire. The behavior is tunable dynamically at runtime via property overrides.

---

### Issue #4: Minotaur Balance
- **Upstream URL**: https://github.com/xanadinn/DurisMUD/issues/4
- **Status in Current Codebase**: **OUTSTANDING (Design Request)**
- **Technical Analysis**:
  - *Request*: *"Mino innates are fucked should be balanced against ogre or firbolg"*.
  - *Current State*:
    - Innates: `INNATE_ULTRAVISION`, `INNATE_CHARGE` (lvl 11), `INNATE_DOORBASH` (lvl 1), `INNATE_DAYVISION` (lvl 1) in `src/innates.c:652-655`.
    - Passive Rage: `src/fight.c:7335` procs `TAG_MINOTAUR_RAGE`.
    - Horn Goring: `src/fight.c:7549` procs headbutt/gore damage in melee combat.
    - Giant Wielding: Single-hands 2-handed weapons via `IS_GIANT(ch)` (`src/actobj.c:94, 5448`).
  - No balancing patch vs Ogres or Firbolgs has been introduced.

---

### Issue #5: 3rd Racewar Side Re-Enabling
- **Upstream URL**: https://github.com/xanadinn/DurisMUD/issues/5
- **Status in Current Codebase**: **OUTSTANDING (Feature Request)**
- **Technical Analysis**:
  - *Request*: *"bring back undead or illithids (or both) depending on # of active players"*.
  - *Current State*:
    - The live roster operates as a standard 2-side war (Good vs Evil, with Neutral races choosing Good or Evil at character creation).
    - Undead forms exist as mid-game `descend` paths (Lich, Vampire, Deathknight, Wight, Revenant, Shadow Beast, Phantom, Shade per `src/constant.c:1644-1654`).
    - Restricted player races (Illithid, Harpy, Sea Giant) are disabled from normal creation unless `CREATION_ALL_RACES=TRUE` is enabled in `.env`.
    - A dynamic, player-population-driven 3rd faction activation system does not exist in the codebase.

---

### Issue #6: Single-Hand Two-Handed Weapons
- **Upstream URL**: https://github.com/xanadinn/DurisMUD/issues/6
- **Status in Current Codebase**: **OUTSTANDING (Feature Request)**
- **Technical Analysis**:
  - *Request*: *"Re-balance single hand 2 handed weapon wielding. fumbles or skill training to enhance"*.
  - *Current State*:
    - In `src/actobj.c:90-102` (`wield_item_size`), any character matching `IS_GIANT(ch)` (`src/utils.h:771`) automatically treats `ITEM_TWOHANDS` and `WEAPON_2HANDSWORD` as size 1.
    - No fumble chance, hit penalties, or prerequisite weapon mastery skill requirements exist for giant-sized races wielding two-handers in one hand.

---
````

#### Comment 1 of 3: `moshehbenavraham`, 2026-08-31

https://github.com/Community-Duris/Duris/issues/63#issuecomment-5478106077

````markdown
@xander-l You can evaluate these :)
````

#### Comment 2 of 3: `moshehbenavraham`, 2026-09-01

https://github.com/Community-Duris/Duris/issues/63#issuecomment-5493848993

````markdown
Historical Item #7 was resolved in a separate thread!
````

#### Comment 3 of 3: `moshehbenavraham`, 2026-09-02

https://github.com/Community-Duris/Duris/issues/63#issuecomment-5504159764

````markdown
@xanadinn @xander-l @Faemill 
````

<a id="issue-474"></a>

### #474: Economy accounting: implement balanced coin transfers and auditable item custody

- Issue: https://github.com/Community-Duris/Duris/issues/474
- Opened by `xander-l` on 2026-09-17
- Labels: `enhancement`, `area:database`, `type:tracking`, `priority:P2`, `area:items`, `area:economy`
- Discussion created: #644 (Ideas)

````markdown
Implement complete double-entry-style coin accounting and auditable item custody across Duris's supported economy paths. Every committed change must identify its source, destination, reason and stable operation ID; all legs of an exchange commit together and retries never apply it twice.

**Planning baseline:** `21121ef7d80a6476d2effc601e28178a72021572` (2026-09-17). Source/schema inspection only; no production data audit or performance qualification is claimed.

Duris already has conserving two-endpoint coin commands, revisioned wallet/bank ledgers, item UIDs/current custody/from-to history, operation-ID inbox/results and recoverable SQL/flat-file transactions. Extend those boundaries. Current shop SQL and flat-file routes differ; auction pending claims and escrow are holdings in their own right. Full coverage must prove these routes rather than infer it from existing generic tests.

## Feature contract

- Coin postings balance in integer copper value per economic operation. Keep denomination vectors for gameplay/reload; use checked arithmetic. Ordinary holdings cannot go negative. Named system issuance/sink/opening accounts explain deliberate supply changes and have narrowly authorized policies.
- Reuse existing critical operation IDs, canonical payload hashes and deterministic child identities. Persist explicit root/child/event links. One validated plan drives both domain state and accounting evidence in one authority transaction; ledger logging after a commit is insufficient.
- Item accounting is per persistent UID. Reuse current custody and immutable transfer events, retaining before/after topology. Creation/admission and destruction are explicit. Do not maintain a second independently writable item-ownership ledger or balance coins against an item's price.
- Holdings include wallet, shared bank, pile contents, escrow, pending refund/proceeds claims and genuine domain treasuries. Count physical pile money once. Derived projections, snapshots and telemetry never mint value.
- Preserve gameplay prices, reward amounts, permission/consent/binding rules, NPC limits and current unsupported-operation refusals. This feature adds accounting; it does not create a new trading UI, rebalance the economy, add an external ledger service, or enable automatic reimbursements.
- Make the tracked supply boundary explicit. Fresh world/reset/NPC assets receive one durable creation or first-admission event before transferring value. Loading previously accounted objects is not creation. Unknown legacy provenance remains unknown.
- SQL and flat-file modes share semantics and fixtures. Enforce bounds on plan size, game-loop work, queueing, journal growth and recovery. No unjournaled fallback for an activated domain.
- Record opening balances at a consistent epoch/revision boundary. Old committed receipts must replay without new entries. Immutable history is corrected only through authorized, current-state-guarded compensating operations.
- Reconcile operation balance, holdings, custody/topology, coverage and intermediary accounts independently. An operation can balance and still be unauthorized; domain policy checks remain mandatory.

## Concrete acceptance example

A 100-gold sale with a 5-gold fee contains coin postings buyer -100, seller +95, fee sink +5, plus item UID transfer seller -1/buyer +1. Coins and that UID balance independently, and the entire exchange commits or rejects together. If funds were already reserved in auction escrow, settlement debits escrow and creates the correct claims instead of debiting the wallet again.

## Implementation and merge order

1. Freeze writer inventory, account/reason contracts and fixtures (01), then implement the pure plan/API (02).
2. Add SQL storage (03). Flat-file storage (04) may be prepared against 02, but merges after 03's shared schema/build/lifecycle registration.
3. Add resumable baseline/activation tooling (05). This does not authorize a live cutover. Implement generic currency transfers (06) and item history integration (08), then issuance/expenses (07).
4. Integrate shops (09), collectors (10), auctions (11) and death/world/recovery (12) after their listed prerequisites. Keep commerce modules separate. Reconciliation/reporting (13) starts on the base 06/08 contract; each later domain must add its own checks before release.
5. Add guarded corrections (14) and lifecycle/restore behavior (15). Qualify all domains, fault boundaries, budgets and enforcement activation together (16).

Only 01 is initially ready. Other slices are blocked on the native dependency graph below. Readiness means prerequisites are merged and their contract/tests are available; label changes are not automatic proof of completion.

## Shared-file ownership

| Surface | Ownership / handoff |
|---|---|
| Accounting specification, writer IDs, account/reason registry and golden fixtures | 01, then explicit amendments requested by consumers |
| New pure accounting headers, codecs, plan validation | 02 |
| Initial SQL schema, common SQL transaction adapter, build/schema/runtime/lifecycle registration | 03; later registrations merge serially |
| Flat-file accounting evidence/recovery and common adapter | 04; shared registration after 03 |
| Baseline/epoch/activation tooling | 05 |
| Generic currency and coin integration | 06, then generic issuance/expense policy in 07 |
| Generic item transfer and topology evidence | 08 |
| Shop / collector / auction repositories and gameplay adapters | 09 / 10 / 11, respectively |
| Combat/corpse/world/recovery accounting orchestration | 12; #469 owns the existing saved-item handoff fix |
| Reconciliation/operator lookup/existing reward-projection adapter | 13; every domain slice contributes its checks |
| Correction preview/apply API | 14 |
| Deletion/reset/export/erasure/retention/backup consumers | 15 |
| Integrated qualification, CI registration, rollout/runbook | 16 |

Shared coordinator/repository edits follow the adapter owner and serial handoff; independently inventing competing transaction APIs is out of scope. Slices may use linked small PRs where the writer inventory demonstrates a larger route, while retaining one accountable issue owner.

## Related work and overlap

- #77, #118, #213: completed coin correctness work to preserve in regression coverage.
- #341, #343, #380: existing admission, publication and unresolved-receipt behavior to reuse.
- #347: merged item command/eligibility boundary; preserve it.
- #258 / #270: existing telemetry roadmap and committed-reward projection. Only source compatibility belongs here; no duplicate telemetry pipeline.
- #331 / #375: existing restitution mechanisms; corrections compose existing authority and do not authorize compensation.
- #126: separate legacy quarantine classification/recovery. Baseline must expose quarantines and must not absorb or bypass that recovery policy.
- #469: hard dependency for slice 12's saved-item recovery acceptance. #467/#468/#470/#471/#473 remain separately owned defects/investigations and become release blockers if their covered journeys fail.
- PR #444 overlaps auction test harnesses. PR #409 is unmerged kingdom crafting/store work; include it in writer coverage only if/when merged and coordinate its adapter requirements.

## Definition of done

- Every in-scope writer in the machine-readable inventory has the correct root operation, counterparts, atomic authority boundary and executable evidence for each supported storage mode.
- No unexplained operation imbalance, state drift, missing source/destination, duplicate event, duplicate UID or restore-as-issuance remains.
- Coin transfers, rewards/costs, shop/collector exchanges, auction escrow/claims, item lifecycle, death/recovery, corrections and administrative lifecycle are covered.
- Fresh install, baseline/upgrade, incompatible-version rejection, reconnect/copyover, lost acknowledgement, crash replay and verified restore are qualified.
- Read-only audit/reconciliation, bounded health metrics, existing reward-report compatibility and protected correction tools are usable.
- Representative measured latency, contention, storage growth and recovery meet budgets frozen before qualification.
- Observation and per-domain enforcement gates, pause/rollback and operator runbooks are delivered. Production execution remains separately authorized.

## Label policy

Use `enhancement`, `area:economy`, `priority:P2` and the relevant existing area labels. The parent uses `type:tracking`; children use exactly one readiness label, initially `status:ready` for 01 and `status:blocked` for the rest. This is planned feature work; existing correctness bugs retain their own priorities.

## Work slices

| Slice | Issue | Initial readiness | Merge prerequisites |
|---|---|---|---|
| 01 | [#475](https://github.com/Community-Duris/Duris/issues/475) — define conservation contracts and inventory every economic writer | ready | none |
| 02 | [#476](https://github.com/Community-Duris/Duris/issues/476) — implement bounded balanced plans and versioned operation links | blocked | #475 |
| 03 | [#477](https://github.com/Community-Duris/Duris/issues/477) — add atomic SQL journal storage and immutable migrations | blocked | #476 |
| 04 | [#478](https://github.com/Community-Duris/Duris/issues/478) — persist accounting evidence atomically in flat-file mode | blocked | #477 |
| 05 | [#479](https://github.com/Community-Duris/Duris/issues/479) — establish opening balances and a restart-safe cutover | blocked | #477, #478 |
| 06 | [#480](https://github.com/Community-Duris/Duris/issues/480) — journal wallet, bank and physical coin transfers | blocked | #479 |
| 07 | [#481](https://github.com/Community-Duris/Duris/issues/481) — account for coin issuance, expenses and authorized adjustments | blocked | #480 |
| 08 | [#482](https://github.com/Community-Duris/Duris/issues/482) — link item custody and lifecycle events to economic operations | blocked | #479 |
| 09 | [#483](https://github.com/Community-Duris/Duris/issues/483) — make shop purchases and sales balanced atomic exchanges | blocked | #481, #482 |
| 10 | [#484](https://github.com/Community-Duris/Duris/issues/484) — journal collector purchases, buybacks and item expiry | blocked | #481, #482 |
| 11 | [#485](https://github.com/Community-Duris/Duris/issues/485) — account for auction escrow, claims, refunds and settlement | blocked | #481, #482 |
| 12 | [#486](https://github.com/Community-Duris/Duris/issues/486) — preserve accounting through death, world lifecycle and recovery | blocked | #481, #482, #469 |
| 13 | [#487](https://github.com/Community-Duris/Duris/issues/487) — add bounded reconciliation, audit queries and reward projection compatibility | blocked | #480, #482 |
| 14 | [#488](https://github.com/Community-Duris/Duris/issues/488) — add audited compensating corrections with current-state guards | blocked | #481, #482, #487 |
| 15 | [#489](https://github.com/Community-Duris/Duris/issues/489) — integrate deletion, season resets, retention and verified restores | blocked | #479, #481, #482 |
| 16 | [#490](https://github.com/Community-Duris/Duris/issues/490) — qualify fault recovery, bounded overhead and full enforcement rollout | blocked | #483, #484, #485, #486, #487, #488, #489 |

## Working agreement

- Read current master and AGENTS.md before implementation; the source baseline below is a planning reference, not a production-validation claim.
- One implementation owner per slice. Claim the issue and owned files before editing; use one cohesive PR or explicitly linked small PRs. Do not assign an invented GitHub user.
- Respect the parent tracker’s shared-file handoffs. Allocate immutable migration numbers on current master at merge; never rewrite sealed migration history. Register durable stores with compatibility/lifecycle changes in the same PR.
- Every behavior change includes meaningful executable regression coverage and the relevant supported-backend journey. Run touched-line formatting and make -C src for C/C++ changes; report exact commands, results and any unavailable checks.
- Preserve exact operation IDs, existing unresolved-receipt fences and post-commit publication. Tests of one persistence mode do not establish support in the other.
- Update the writer coverage inventory, related reconciliation adapters and dependent readiness labels when the slice lands. A missing integration stays blocked rather than becoming an undocumented fallback.
- Use synthetic/redacted fixtures; keep credentials, player identities, raw UIDs from live data and private recovery evidence out of public issues. Production migration/deployment or instance restitution requires separate owner authorization.

<!-- economy-accounting-2026-09-17:parent -->
````

#### Comment 1 of 18: `RGitGoin`, 2026-09-18

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5730977217

````markdown
Claiming ownership of the full economy-accounting feature and ordered slices #475-#490 in codex/474-economy-accounting. The user explicitly authorized implementation, ownership claim, and one final PR for xander-l review. Base refreshed to current master 440248b17eecc3517229a48a4946cf6c0a33ffa5. I will integrate and qualify all slices in dependency order on this branch and submit no partial PRs. Initial owned files: docs/persistence/ECONOMY_ACCOUNTING.md, the accounting writer inventory/account-reason registry/golden fixtures, their validator, then new economic_accounting_* API/storage and listed domain adapters through serial handoffs. Existing separately owned defects remain explicit dependencies. Production migration/deployment/restitution are outside this authorization.
````

#### Comment 2 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5764281890

````markdown
Continuing ownership of #474 and #475-#490. The user has approved phased delivery, superseding my earlier one-final-PR/no-partial-PR statement. The full feature acceptance criteria remain unchanged.

The first linked foundation PR is being prepared on `codex/474-phase1-foundation`, based on canonical master `48c0aedd8e094eee37285111e46e735e4cf12320`. Initial ownership: accounting contract/registry/fixtures/writer inventory and validator, pure accounting types/plan codecs and their focused tests, plus narrow build/test registration. Storage activation, gameplay callers and broader item persistence are outside this first extraction. The existing integration branch is preserved.

Later PRs will deliver storage, a complete wallet/bank journey, remaining core writers, separate commerce/recovery domains, and operational/lifecycle qualification in dependency order. Incomplete slices remain open and activation stays disabled until all writers touching the relevant holdings are covered. Current master's migration 0030 is already occupied by telemetry; accounting migration allocation will be reconciled in the storage PR without rewriting deployed history.

Each PR will request xander-l review. Production cutover, deployment and restitution remain outside this authorization.
````

#### Comment 3 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5764488747

````markdown
First phased deliverable: #599, pure economy accounting foundation, based on canonical master 48c0aedd8e094eee37285111e46e735e4cf12320. Head a63ae0d26c4060d21054a6056009b7ece8f8ef60.

It adds the contract/registry/13 fixtures, a current-master inventory (115 routes, 2,731 lexical candidates; semantic coverage explicitly incomplete), bounded accounting types and canonical plan codec. No stores, migrations, gameplay callers or activation changes. #475 and #476 remain open as partially addressed.

Validation passed: 26 contract regressions, draft validator and expected release refusal, ASan/UBSan pure types/plan harnesses, canonical SQL/flat-file compilation parity, both full server builds, formatting and diff checks. Review found and fixed an omitted owner-context comparison in the Python topology model.

Requested xander-l review in a PR comment after GitHub denied the formal reviewer operation for insufficient permissions. Next dependency-ordered increment: frozen intent and guarded command envelopes, then SQL/flat-file storage. The original integration branch remains preserved.
````

#### Comment 4 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5764530331

````markdown
Continuing #474 with the next dependent increment on `codex/474-phase2-intents`, based on #599 head a63ae0d26c4060d21054a6056009b7ece8f8ef60. Ownership: frozen accounting intent codec, critical-command wire envelope and explicit legacy execution guards, affected SQL repository entrypoints, focused codec/admission/replay tests and corresponding contract documentation.

This increment keeps schema-2 commands unsupported by admission and mutation paths until typed accounting storage is integrated. Existing schema-1 behavior and bytes must remain compatible. No migrations, gameplay activation or production actions. The implementation will preserve current-master changes while reusing the already-built integration-branch component. Review/merge remains dependency-ordered behind #599.
````

#### Comment 5 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5764789156

````markdown
Second phased increment: dependent draft #600, frozen intents and guarded accounting envelopes, head 9cd153f3c11217fa17895b48df4e52d78594bf9b. It is one commit / 31 files beyond #599 and must follow that foundation in merge order.

Verified bounded wire compatibility and fail-closed execution: both server builds; plan/intent sanitizer/reference tests; 26 contract tests; direct SQL rejection before connection access; 34 representative flat-file refusals with unchanged authority files; mixed-journal retention without authority apply/checkpoint; legacy coordinator/admission/journal regressions. No stores, migrations, gameplay activation or completed child issues.

Known prerequisite retained: the existing boon result is 2080 bytes while the completion buffer is 2048. The compiler diagnostic reproduces on clean #599, and the preserved integration branch already contains focused fix 27222aea4. This remains required before reward/receipt integration; successful boon behavior is not claimed by the unoptimized sanitizer gate. Unrelated baseline corpse formatting drift is also recorded without expanding this diff.

Requested xander-l review in the PR comments because formal reviewer assignment is unavailable to this account. Remaining contract decisions/site classification and the boon prerequisite stay explicit before advancing storage/reward integration.
````

#### Comment 6 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5764849332

````markdown
Claiming the required boon completion-buffer prerequisite on `codex/474-boon-completion`, independently based on canonical master 48c0aedd8e094eee37285111e46e735e4cf12320. Owned surfaces: critical completion capacity, SQL/flat-file boon capacity assertions, the persisted player-domain receipt bound, and focused completion/boon regression harnesses. Reusing the preserved focused fix 27222aea4.

The confirmed defect is a 2080-byte boon result copied into a 2048-byte completion buffer. The change will preserve the existing persisted player-domain format limit while carrying full supported results through completion/replay. This is a prerequisite for #481/receipt integration, not accounting activation. It can be reviewed separately from #599/#600; no production actions.
````

#### Comment 7 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5765090800

````markdown
Phased delivery update: standalone prerequisite PR #601 is ready for review at `004598b0eb996b50cddaa964ac05ea09ebdda046`, with an @xander-l review request in its comments. It fixes the existing 2,080-byte boon result overflowing the 2,048-byte completion buffer and preserves native player-domain receipt format limits. It can merge independently of foundation #599 and guarded-envelope draft #600.

Local validation passed: full flat-file and MariaDB server builds; ASan/UBSan full-result delivery/replay and boon regressions; native formats 2/3 receipt bounds; disposable MySQL 8.0.46 and MariaDB 10.11.14 SQL replay/receipt checks. Hosted quality currently fails formatting in 14 untouched base files; other hosted checks are pending.

#474 and its child acceptance gates remain open. Next work stays within contract completion and guarded storage integration, followed by the first complete wallet/bank journey. This fix does not enable accounting or change the phased delivery scope.
````

#### Comment 8 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5765478643

````markdown
Phased delivery: draft PR #602 now contains the SQL storage/identity-lock increment at `2472569283bde6fdb2104e953837e2e95e7292be`, based on #600. @xander-l review requested in its comments. Nine retained tables, provisional migration0031, bootstrap/runtime/lifecycle registration, and transaction-borrowing identity locks are included. Existing immutable history is byte-identical.

Both MySQL8.0.46 and MariaDB10.11.14 passed fresh bootstrap, separate canonical0030 upgrades, replay, schema tests and runtime verification. Final authority tests include contention, lifetime reuse, cross-lineage mismatch and disconnect; client-free refusal and both server builds pass. Full details and incremental comparison are in the PR.

#477/#474 remain open. Next: reuse the existing typed SQL bank transaction component, bind append/finalize to actual locked domain effects and retained receipts, and qualify root commit/rollback/replay without enabling gameplay prematurely. Compound adapters, append-only access protections, other backends/writers and the remaining original acceptance gates are still required.
````

#### Comment 9 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5765841856

````markdown
Phased delivery update: draft #603 adds typed SQL bank direct-root execution and replay on top of #602 storage and #601 boon prerequisite. Local native MySQL/MariaDB fault suites, legacy currency regressions, both builds and focused sanitizer/flatfile recovery checks pass. #602 also now fixes the hosted socket migration argument-order failure (edd040cea), without changing sealed migration bytes. Review requested from @xander-l by comment; hosted qualification is pending. Gameplay remains inactive. Next delivery must connect and qualify transport/backend admission and maintenance baseline/publication toward the first complete wallet/bank journey. No child issue is closed by this increment.
````

#### Comment 10 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5766071163

````markdown
Published linked draft #604 for SQL bank durable admission/replay, following #603. Local native MySQL/MariaDB pooled-bank fault/replay tests, coordinator sanitizer tests and both server builds pass. #602/#603 hosted disposable recovery and flatfile builds now pass; inherited formatting failures remain documented. Next dependency is #478 flatfile accounting storage and transaction ownership, reusing preserved work, before qualifying the complete both-backend baseline/gameplay/publication journey. No child issue is closed by this increment.
````

#### Comment 11 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5766293051

````markdown
Phased update: published draft #605 for bounded flat-file evidence storage following #604. Reused preserved implementation with required pending-journal/allocation/hardlink fixes; native sanitizer fault suites and both full builds pass. This adds protected retained storage without gameplay activation. Next: retained flat-file lifetime/epoch metadata and typed bank transaction ownership, then baseline and native gameplay/publication qualification. No child issue is closed by this increment.
````

#### Comment 12 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5766542809

````markdown
Published linked draft #606 for retained flat-file lifetime/epoch metadata. Both builds, native authority/storage sanitizer suites and registration checks pass locally. Also corrected #605 boot topology expectations; its hosted flatfile-build and recovery workflow now pass. Next is the typed flat-file bank owner with borrowed-lock native reads, followed by baseline and gameplay/publication qualification. No child issue is closed by this increment.
````

#### Comment 13 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5766741910

````markdown
Phased delivery update: draft PR #607 adds the standalone typed flat-file bank owner on #606, at 7906655852d624dbda598aa1afae357c1fba8381. Ownership claim was posted before implementation. @xander-l review requested by PR comment.

Local verification passed: both native ASan/UBSan suites, 608 bank allocation failures including 224 during/after commit, journal-only and four image crash boundaries, forged evidence, retained replay and contention; existing identity/domain regressions; 26 contracts/census/formatting; full flat-file and MariaDB builds. Hosted CI remains pending.

Next deliverable is bank-only flat-file backend dispatch/admission. Gameplay, maintenance baseline, lifecycle ownership, other writer coverage and final qualification remain open. This component does not close #478 or any other #474 child issue and does not activate production accounting.
````

#### Comment 14 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5766982081

````markdown
Next linked deliverable published: draft PR #608 at 190602263f0249b4859981ab7733e14bb469f5e4, based on #607, connects flat-file bank dispatch and admission. @xander-l review requested by comment.

Native sanitizer tests prove exact original-ID/timestamp replay with one balance mutation, fresh acknowledgement retirement and unsupported durable-work refusal. Existing admission/default-gate tests, census/formatting, both full builds and disposable flat-file boot passed. Hosted CI pending.

The native journey exposed replay auto-retirement without restored publication retention. This is tracked explicitly as required bank gameplay recovery work before activation, not claimed fixed. Committed bank balances reload from native authority; no lost-balance finding is established here.

Next reusable component: pure baseline preparation and source-witness codecs, followed by native baseline/enrollment and the required maintenance/publication boundary. All #474 child issues remain open; this does not activate accounting or complete a player journey.
````

#### Comment 15 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5767199698

````markdown
Linked baseline preparation deliverable published as draft PR #609 at 5fd726388e453c7e08d95b480b0c04c928e405f6, based on #608. Ownership was claimed before edits; @xander-l review requested by PR comment.

Both SQL/client-free ASan/UBSan suites passed independent witness/payload references, canonical/malformed/max-size cases, native revision preservation and allocation sweeps. Real coordinator refusal proves baseline commands cannot execute or checkpoint. Existing plan/intent goldens, bank admission, mixed-journal refusal, 26 contracts, census/formatting and both full server builds passed. Hosted CI pending.

This is pure preparation and command binding. Native source capture, baseline persistence, maintenance cutover ownership, publication/save recovery and activation remain open. Next linked component is flat-file baseline witness/reservation storage, with lifecycle/backup registration and current journal/failure-stage compatibility. No #474 child issue is closed and no production operation is authorized by this PR.
````

#### Comment 16 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5767382054

````markdown
Linked flat-file baseline storage is published as draft PR #610 at a039c6c9446b01c8262fdc6b44354f8f82a20627, based on #609. @xander-l review requested by comment.

Local qualification passed: 41 native restart boundaries, 606 staging and 419 lookup allocation failures, duplicate/replay/epoch/max-witness cases, failure-stage tamper/hardlink/pending-journal refusal; shared storage85 fault cases; lifecycle11, backup4, contracts26, census/formatting; full flat-file and MariaDB builds. Hosted CI pending.

Lifecycle registration includes all three baseline classes and their previously unregistered existing v2 transaction-journal dependency. No new journal format, production lifecycle owner, baseline admission or activation is added.

Next deliverable: SQL baseline schema and private transaction owner, with fresh migration/runtime fingerprints and native engine verification. Source capture/enrollment, maintenance cutover, publication/save acknowledgement and all remaining coverage remain open. No #474 child issue is closed by this component.
````

#### Comment 17 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5767783549

````markdown
Published the next phased component: PR #612 at dab03b0e6cbb8d8bf47992313c26c24c02455977, following #610. It adds private SQL baseline witness retention and per-epoch identity reservations, migration0032 and lifecycle/runtime registration. Fresh installs, actual0031 upgrades, schema enforcement, native transaction faults and 50 MariaDB concurrency rounds passed. The concurrency test now handles proven1213 deadlock victims with bounded fresh-session original-ID retry; production locking is unchanged.

This is storage-component progress, not completion of #479 or gameplay activation. Next are authenticated native source capture and wallet/shared-bank enrollment, then maintenance cutover ownership and restart-safe publication/save acknowledgement for the first complete journey. All16 child issues remain open; no production migration/deployment occurred. @xander-l review requested on the linked PR.
````

#### Comment 18 of 18: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/474#issuecomment-5767962748

````markdown
Published the next phased component, PR #613 at 084bdc3ce130377cc22b395c4155586cbcae0ba8, following #612. It captures 18 selected native SQL sources under one bounded read-only snapshot and normalizes money/custody evidence with explicit unresolved diagnostics. It changes no native balances, UIDs, custody or schema.

MySQL/MariaDB ASan/UBSan suites passed 58 query faults, 107 capture allocation faults and 125 normalization allocation faults per engine, plus snapshot/DDL/session/capacity/disconnect/lost-ACK fixtures and client-free checks. Both full server builds and 26 contract tests passed. Writer coverage remains unchanged; no child-issue completion is claimed.

The next wallet/shared-bank enrollment component can use this capture directly without importing the later physical/auction/collector expansions. Real lifecycle ownership, authorization, a retained maintenance boundary and restart-safe publication/save acknowledgement still remain before the first complete gameplay journey. @xander-l review requested. No production capture or deployment occurred.
````

<a id="issue-475"></a>

### #475: Economy accounting [01/16]: define conservation contracts and inventory every economic writer

- Issue: https://github.com/Community-Duris/Duris/issues/475
- Opened by `xander-l` on 2026-09-17
- Labels: `documentation`, `enhancement`, `area:database`, `status:ready`, `priority:P2`, `area:items`, `area:economy`
- Discussion created: #645 (Ideas)

````markdown
Parent: #474

**Slice:** 01/16 · **Priority:** P2 · **Readiness:** ready

**Merge prerequisites:** none

Coin transfers already check conservation and item transfers already record from/to custody, but there is no complete accounting contract covering every economy writer, backend, lifecycle boundary, and intermediate holding account. Establish the implementation contract before storage or gameplay integration diverges.

## Scope

- Publish docs/persistence/ECONOMY_ACCOUNTING.md and a machine-readable writer coverage inventory. These are proposed deliverables. Record each command/repository/call site, persistence mode, authority boundary, economic reason, source/destination, current support, integration slice, and executable test.
- Define stable account identities for player wallets, shared account/racewar banks, coin-pile UIDs, auction escrow and pending claims, shops/collectors where economically applicable, named issuance/sink accounts, opening balances, and correction accounts. Use immutable identities or durable mappings rather than mutable names, VNUMs, pointers, or recycled runtime IDs.
- Specify integer copper value (1/10/100/1000), retained denomination vectors, checked arithmetic, normal-account non-negativity, allowed system-account signs, per-operation balance, unique item custody, same-owner topology changes, and grouping existing child operations under one economic operation.
- Inventory normal and exceptional routes: give/get/drop/put/bank/split, rewards and costs, creation/starter/admin/import, shops/collectors/auctions, NPC/reset/crafting/consumption, death/corpse/restoration, extraction, character deletion and season reset. Inventory currently transient exceptions rather than silently manufacturing durable NPC authority.
- Define the admission boundary: every transferable asset enters accounting exactly once through durable creation or a documented first admission. Recovery/load/materialization is not new issuance. State the covered supply boundary and how legacy/unknown evidence is reported.
- Freeze backend-neutral fixtures, bounded plan sizes and error semantics, versioning/cutover policy, coverage states (legacy/observed/enforced), immutable correction rules, and rollout gates. Preserve current gameplay economics and current refusals for unsupported custody.

## Acceptance criteria

- [ ] Every identified coin or item writer has one named integration owner and a source/sink classification; bypasses and unsupported operations are visible and block claims of full coverage.
- [ ] Golden examples include wallet/bank, wallet/pile with making change, a multi-recipient split, reward, expense, item/container move, shop sale and staged auction settlement; coins and each item UID balance independently.
- [ ] Contract distinguishes economic commit, live publication, snapshots, telemetry, and operation-ID replay. It prohibits arbitrary balancing adjustments and treats ambiguous receipts as unresolved.
- [ ] Existing bug ownership and pending PR #409 are recorded without assuming unmerged behavior or duplicating those fixes. Estimates and any scope splits are refined after the census.

## Validation

Review the inventory against searches of actual state mutations and ledger writers on current master. Add a small inventory/fixture validator that detects duplicate or missing IDs, invalid dependency references, unknown account/reason types, and invalid golden examples. This issue does not change gameplay.

## File ownership and interfaces

Own the public accounting specification, fixture format, writer IDs and source/sink registry contract. Storage/API issues consume this contract; amendments remain explicit.

## Working agreement

- Read current master and AGENTS.md before implementation; the source baseline below is a planning reference, not a production-validation claim.
- One implementation owner per slice. Claim the issue and owned files before editing; use one cohesive PR or explicitly linked small PRs. Do not assign an invented GitHub user.
- Respect the parent tracker’s shared-file handoffs. Allocate immutable migration numbers on current master at merge; never rewrite sealed migration history. Register durable stores with compatibility/lifecycle changes in the same PR.
- Every behavior change includes meaningful executable regression coverage and the relevant supported-backend journey. Run touched-line formatting and make -C src for C/C++ changes; report exact commands, results and any unavailable checks.
- Preserve exact operation IDs, existing unresolved-receipt fences and post-commit publication. Tests of one persistence mode do not establish support in the other.
- Update the writer coverage inventory, related reconciliation adapters and dependent readiness labels when the slice lands. A missing integration stays blocked rather than becoming an undocumented fallback.
- Use synthetic/redacted fixtures; keep credentials, player identities, raw UIDs from live data and private recovery evidence out of public issues. Production migration/deployment or instance restitution requires separate owner authorization.

## Source references

Planning baseline: `21121ef7d80a6476d2effc601e28178a72021572`. Verify drift before implementation. New paths named in scope are proposed deliverables, not existing files.

- [src/economy/coin_transfer_command.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/coin_transfer_command.c)
- [src/economy/currency_command.h](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/currency_command.h)
- [src/item/item_transfer_command.h](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/item/item_transfer_command.h)
- [docs/persistence/ITEM_COMMAND_PIPELINE.md](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/docs/persistence/ITEM_COMMAND_PIPELINE.md)
- [src/economy/shop.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/shop.c)
- [src/economy/auction_repository.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/auction_repository.c)

<!-- economy-accounting-2026-09-17:01 -->
````

#### Comment 1 of 4: `RGitGoin`, 2026-09-18

https://github.com/Community-Duris/Duris/issues/475#issuecomment-5730977533

````markdown
Claiming slice 01 under parent #474 in codex/474-economy-accounting. Own docs/persistence/ECONOMY_ACCOUNTING.md, machine-readable writer coverage inventory, stable account/reason registry, golden fixtures and validator. Current implementation baseline 440248b17eecc3517229a48a4946cf6c0a33ffa5. All sixteen slices will be integrated in dependency order into one final PR per the user; no claim of completed coverage or activation until qualified.
````

#### Comment 2 of 4: `xander-l`, 2026-09-20

https://github.com/Community-Duris/Duris/issues/475#issuecomment-5752441655

````markdown
Creation-grant caller audit found additional writers that should be recorded in this inventory and aligned with the eventual accounting contracts:

- #551: Mix Poison, Mix Potion, Encrust, and the Harvester soul-shard exchange can consume authoritative inputs before the asynchronous output grant commits. This is an independently actionable P1 conservation/lifetime defect and should not wait for the full accounting rollout.
- #550: Summon Book, Summon Totem, and Soulbind reload retire prior state before replacement publication; three conjured-weapon spells charge HP before delivery commits.
- #549: trusted Soulbind and rogue Slip are remaining existing-UID player-to-player transfer writers discovered after #524.
- #548: Wind Blade exposed a committed-creation publication/reconciliation hole; include its creation/reconciliation outcome identities where the inventory covers item lifecycle writers.

Please include the exact source writers, stable operation/reason identity, input/output or source/destination legs, current atomicity boundary, and focused fixtures. The new correctness tickets remain `status:ready`; linking them here is for contract reuse and coverage, not to make them wait on every #474 slice.
````

#### Comment 3 of 4: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/475#issuecomment-5765118832

````markdown
Continuing ownership of the contract follow-up in foundation PR #599: docs/persistence/ECONOMY_ACCOUNTING.md and economy_accounting/writers.json. I will record source-verified route semantics and distinguish remaining implementation dependencies from undecided policy. Coverage/backend qualification stays unverified; no gameplay changes or new global atomicity requirement.
````

#### Comment 4 of 4: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/475#issuecomment-5765186123

````markdown
Contract follow-up pushed at `881663d68946bd80f72f720a2e5c368711023c3b` for @xander-l review. Clarifies 10 existing writer classifications: split recipient/remainder rules, floor/NPC transfer boundaries, pending-claim attribution, blackjack stake/loss/fold/reset, finite keeper cash exception, auction no-reimbursement behavior, chaos-pouch material variants, and refinement's intended destruction outcome and combined ore/coin costs.

Source review corrected overly broad pouch consumption wording and distinguished committed gameplay failure from technical failure. No gameplay, codec, storage, or backend qualification changes. Draft validation and all 26 contract tests pass; --release still correctly refuses missing executable writer evidence. Coverage remains 115 routes / 2,731 lexical candidates and incomplete. Previous native build evidence applies to unchanged C++ code, not a new build of this documentation-only head.

The dependent #600 now includes this same contract amendment at `511d04f16b613a000a857af4293fcd8b2d3fb48a`; its draft status remains appropriate.
````

<a id="issue-476"></a>

### #476: Economy accounting [02/16]: implement bounded balanced plans and versioned operation links

- Issue: https://github.com/Community-Duris/Duris/issues/476
- Opened by `xander-l` on 2026-09-17
- Labels: `enhancement`, `area:database`, `status:blocked`, `priority:P2`, `area:items`, `area:economy`
- Discussion created: #646 (Ideas)

````markdown
Parent: #474

**Slice:** 02/16 · **Priority:** P2 · **Readiness:** blocked

**Merge prerequisites:** #475

Each domain currently constructs its own changes. A shared accounting plan must prove conservation and match the actual domain mutations before either storage backend can commit it.

## Scope

- Add a narrow pure accounting module under src/economy/ (proposed economic_accounting_* files) with stable account keys, integer coin postings, item-event references, reason/actor metadata, plan version, and root-to-child operation links.
- Use the existing critical operation ID and deterministic child IDs. Bind the canonical plan digest/version to replay identity; identical replay returns the original outcome and different bytes under the same ID fail closed.
- Validate sums with checked wider intermediates before narrowing, denomination/value agreement, limits, source/destination identities, duplicate item references, source/sink capability rules, and ordered entity keys. A row-level SQL CHECK alone cannot validate a whole operation.
- Require exact agreement between the frozen plan, authoritative before/after domain state, and posting lines. Internal typed adapters choose allowed counterparties; generic callers cannot select an issuance account to hide an imbalance.
- Keep the existing coordinator and worker lifecycle. Define transactional adapter hooks and committed result publication; do not add a second command queue or generic event-sourcing engine.

## Acceptance criteria

- [ ] Malformed, unbalanced, overflowing, over-limit, duplicate, mismatched, or unauthorized plans fail before durable state or success publication.
- [ ] Valid multi-leg transfers and same-owner item topology changes are expressible without netting away their audit evidence.
- [ ] Canonical serialization and deterministic operation relationships are identical across storage modes and persist enough evidence to reconstruct a compound operation.
- [ ] Supported legacy payloads retain exact replay behavior; unknown incompatible versions fail closed. No plan retains mutable game pointers.

## Validation

Pure executable and property-based tests cover all golden fixtures, permutation/canonicalization, maximum sizes, integer extremes, malformed versions, and duplicate/mismatched operation IDs. Use ASan/UBSan where supported; run formatting and make -C src for C++ changes.

## File ownership and interfaces

Own new accounting headers/codecs/builders and their isolated tests. Coordinate the narrow coordinator dispatch interface with slice 03; gameplay slices supply domain-specific adapters.

## Working agreement

- Read current master and AGENTS.md before implementation; the source baseline below is a planning reference, not a production-validation claim.
- One implementation owner per slice. Claim the issue and owned files before editing; use one cohesive PR or explicitly linked small PRs. Do not assign an invented GitHub user.
- Respect the parent tracker’s shared-file handoffs. Allocate immutable migration numbers on current master at merge; never rewrite sealed migration history. Register durable stores with compatibility/lifecycle changes in the same PR.
- Every behavior change includes meaningful executable regression coverage and the relevant supported-backend journey. Run touched-line formatting and make -C src for C/C++ changes; report exact commands, results and any unavailable checks.
- Preserve exact operation IDs, existing unresolved-receipt fences and post-commit publication. Tests of one persistence mode do not establish support in the other.
- Update the writer coverage inventory, related reconciliation adapters and dependent readiness labels when the slice lands. A missing integration stays blocked rather than becoming an undocumented fallback.
- Use synthetic/redacted fixtures; keep credentials, player identities, raw UIDs from live data and private recovery evidence out of public issues. Production migration/deployment or instance restitution requires separate owner authorization.

## Source references

Planning baseline: `21121ef7d80a6476d2effc601e28178a72021572`. Verify drift before implementation. New paths named in scope are proposed deliverables, not existing files.

- [src/persistence/critical_command.h](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/persistence/critical_command.h)
- [src/economy/coin_transfer_command.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/coin_transfer_command.c)
- [src/item/item_transfer_command.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/item/item_transfer_command.c)
- [src/persistence/critical_command_coordinator.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/persistence/critical_command_coordinator.c)

<!-- economy-accounting-2026-09-17:02 -->
````

#### Comment 1 of 3: `RGitGoin`, 2026-09-18

https://github.com/Community-Duris/Duris/issues/476#issuecomment-5731241142

````markdown
Ownership claim for #476 under the explicitly authorized full #474 implementation. I own the new src/economy/economic_accounting_* pure plan types, validators/codecs and focused executable tests, plus the narrow critical-command envelope interface after compatibility review. Work is on codex/474-economy-accounting, based on 440248b17eecc3517229a48a4946cf6c0a33ffa5.

The #475 contract/census is still being completed; this is an implementation ownership reservation, not a readiness or completion claim. Interfaces remain draft until the contract and backend qualifications are settled. The complete series will be submitted as one final PR for xander-l, with no partial PRs. Existing command IDs, payload capacity, receipt fences and publication ordering remain required.
````

#### Comment 2 of 3: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/476#issuecomment-5765882462

````markdown
Claiming the next linked #474 increment: typed bank coordinator admission and original-ID durable replay, paired explicitly with the supported SQL bank root. Owned paths: economic_command_admission, critical_command_coordinator, the SQL pool wrapper, server startup registration and focused admission tests/docs. Reuse preserved implementation a89fa8f18 with bank-only/backend-aware support matching #603. Flatfile accounting and unsupported families remain refused until their owners are delivered. No gameplay producer or activation is enabled by this increment.
````

#### Comment 3 of 3: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/476#issuecomment-5766070836

````markdown
Ownership update: draft PR #604 delivers the bank-only typed coordinator admission and original-ID replay increment at 0bb3c3754, dependent on #603. SQL startup explicitly pairs the validator with the pooled bank root; flatfile/default callers retain refusal. Fresh timestamp assignment and publication acknowledgement fences are tested, alongside real pooled MySQL/MariaDB commit/replay/replacement-connection recovery and both full builds. @xander-l review requested by comment. This is partial delivery; #476 remains open.
````

<a id="issue-477"></a>

### #477: Economy accounting [03/16]: add atomic SQL journal storage and immutable migrations

- Issue: https://github.com/Community-Duris/Duris/issues/477
- Opened by `xander-l` on 2026-09-17
- Labels: `enhancement`, `area:database`, `status:blocked`, `priority:P2`, `area:economy`
- Discussion created: #647 (Ideas)

````markdown
Parent: #474

**Slice:** 03/16 · **Priority:** P2 · **Readiness:** blocked

**Merge prerequisites:** #476

Normalized coin postings and compound-operation relationships must become durable in the same SQL transaction as existing balances, custody, inbox/results and outbox. A best-effort audit insert would leave an unexplained commit window.

## Scope

- Add additive InnoDB schema for an accounting operation record linked to the existing root inbox ID, coin posting lines, and explicit references to existing item ledger events and child operations. Include epoch/version, canonical digest, bounded line counts, reason metadata and query indexes. Exact names follow slice 01.
- Provide transaction-local append/finalize helpers; they must never open a separate connection or commit internally. Verify the complete plan and actual effects before the parent transaction commits, including compound savepoint rejection paths.
- Retain current balance/custody tables as the read model updated by the same plan, and preserve existing currency/item ledgers during compatibility rollout. Keep rejected/ambiguous receipts distinct from committed postings.
- Enforce unique operation/line and source-event relationships; use application-role protections and repository APIs to make financial evidence append-only while preserving authorized migration/backup access.
- Allocate the next immutable migration IDs at merge time and update verifiers, bootstrap, migration/runtime fingerprints, and lifecycle registration in the same change. Do not edit sealed historical migrations.
- Use deterministic row locks and bounded indexes; avoid a globally contended mutable mint/sink total row when totals can be derived from immutable entries.

## Acceptance criteria

- [ ] Injected failure after any domain update or posting write leaves no partial committed operation; a complete commit has all required entries, domain state, receipt and outbox.
- [ ] Lost COMMIT acknowledgement and deadlock retries use the original ID and produce one committed operation; changed payload under that ID fails.
- [ ] Missing/extra entries and mismatched actual state are rejected at the repository commit boundary, including specialized writers using the adapter.
- [ ] Fresh bootstrap, supported upgrades and replay of migrations agree on schema/runtime/lifecycle contracts in MySQL and MariaDB.

## Validation

Extend disposable SQL transaction harnesses with multi-account transfers, item references, savepoint rejection, duplicate IDs, commit ambiguity, same-bank participants, lock contention and invariant failures. Run immutable migration, runtime compatibility and lifecycle verification on both supported engines.

## File ownership and interfaces

Own initial SQL schema and shared manifest/build registration, plus the common SQL commit adapter. Subsequent schema changes merge serially after this issue; other slices request small interface changes rather than editing the same transaction core independently.

## Working agreement

- Read current master and AGENTS.md before implementation; the source baseline below is a planning reference, not a production-validation claim.
- One implementation owner per slice. Claim the issue and owned files before editing; use one cohesive PR or explicitly linked small PRs. Do not assign an invented GitHub user.
- Respect the parent tracker’s shared-file handoffs. Allocate immutable migration numbers on current master at merge; never rewrite sealed migration history. Register durable stores with compatibility/lifecycle changes in the same PR.
- Every behavior change includes meaningful executable regression coverage and the relevant supported-backend journey. Run touched-line formatting and make -C src for C/C++ changes; report exact commands, results and any unavailable checks.
- Preserve exact operation IDs, existing unresolved-receipt fences and post-commit publication. Tests of one persistence mode do not establish support in the other.
- Update the writer coverage inventory, related reconciliation adapters and dependent readiness labels when the slice lands. A missing integration stays blocked rather than becoming an undocumented fallback.
- Use synthetic/redacted fixtures; keep credentials, player identities, raw UIDs from live data and private recovery evidence out of public issues. Production migration/deployment or instance restitution requires separate owner authorization.

## Source references

Planning baseline: `21121ef7d80a6476d2effc601e28178a72021572`. Verify drift before implementation. New paths named in scope are proposed deliverables, not existing files.

- [src/persistence/critical_command_repository.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/persistence/critical_command_repository.c)
- [migrations/currency_ledger.sql](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/migrations/currency_ledger.sql)
- [migrations/item_ownership_ledger.sql](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/migrations/item_ownership_ledger.sql)
- [migrations/migration_manifest.json](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/migrations/migration_manifest.json)
- [migrations/runtime_compatibility_manifest.json](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/migrations/runtime_compatibility_manifest.json)
- [tests/async/currency_transaction_mysql_harness.cpp](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/tests/async/currency_transaction_mysql_harness.cpp)

<!-- economy-accounting-2026-09-17:03 -->
````

#### Comment 1 of 6: `RGitGoin`, 2026-09-18

https://github.com/Community-Duris/Duris/issues/477#issuecomment-5732212524

````markdown
Claiming implementation ownership under the authorized full #474 effort for the SQL critical-command repository and coordinator integration, including accounting envelope execution gates and later atomic accounting hooks. Work is isolated on `codex/474-economy-accounting`. This remains incomplete and dependent on the preceding contract/API work; no readiness or validation claim is implied. The full effort will be submitted as one final PR for `xander-l` review.
````

#### Comment 2 of 6: `RGitGoin`, 2026-09-18

https://github.com/Community-Duris/Duris/issues/477#issuecomment-5732373242

````markdown
The #477 shared SQL integration work also owns the schema-only execution guard at every public command-bearing SQL mutation entrypoint: currency, item transfers, auction, collector (including its boundary/enrollment sidecars), boon, corpse lifecycle, death restitution, combat, artifact/guild, zone and session audit. These guards reject the newly serializable accounting envelope until typed atomic accounting execution is integrated; they do not change legacy domain payload policy. Domain accounting implementation and qualification remain incomplete.
````

#### Comment 3 of 6: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/477#issuecomment-5765240325

````markdown
Claiming the phased SQL storage follow-up on codex/474-phase3-sql-storage, based on guarded-envelope PR #600. Ownership covers accounting SQL schema, its complete migration/bootstrap/runtime/lifecycle registration, transaction-borrowing identity-lock helper and focused tests. Reusing preserved bb8c1e5c5 and 0dc1079fd selectively; current master uses 0030 for telemetry, so accounting will use provisional 0031 and recheck before merge. Schema-2 execution stays refused. Typed append/finalize and domain commit integration remain required before #477 can close.
````

#### Comment 4 of 6: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/477#issuecomment-5765478160

````markdown
Phased delivery: draft PR #602 now contains the SQL storage/identity-lock increment at `2472569283bde6fdb2104e953837e2e95e7292be`, based on #600. @xander-l review requested in its comments. Nine retained tables, provisional migration0031, bootstrap/runtime/lifecycle registration, and transaction-borrowing identity locks are included. Existing immutable history is byte-identical.

Both MySQL8.0.46 and MariaDB10.11.14 passed fresh bootstrap, separate canonical0030 upgrades, replay, schema tests and runtime verification. Final authority tests include contention, lifetime reuse, cross-lineage mismatch and disconnect; client-free refusal and both server builds pass. Full details and incremental comparison are in the PR.

#477/#474 remain open. Next: reuse the existing typed SQL bank transaction component, bind append/finalize to actual locked domain effects and retained receipts, and qualify root commit/rollback/replay without enabling gameplay prematurely. Compound adapters, append-only access protections, other backends/writers and the remaining original acceptance gates are still required.
````

#### Comment 5 of 6: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/477#issuecomment-5765526678

````markdown
Claiming the typed SQL bank follow-up on codex/474-phase4-sql-bank. Own currency prepared-mutation/typed bank adapter, bank transaction component, critical root apply/replay integration, relevant build/test registration and scoped documentation. Reuse preserved 3bc96367e/a7db124eb/316fd1786 plus retained-rejection fix b24e4004f. Base is #602; include independent boon prerequisite #601 for the native sanitized repository harness. No gameplay producer activation, generic caller-plan append API, broader coin or baseline integration in this increment.
````

#### Comment 6 of 6: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/477#issuecomment-5765841568

````markdown
Ownership update: published draft PR #603 for typed SQL bank direct-root transactions, dependent on #602 and #601. Incremental commit 826b6ac71 includes atomic domain/evidence/inbox completion, exact-ID retained replay and rejection/failure-stage tamper checks. Native MySQL/MariaDB fault/replay and legacy currency regressions pass; both server builds pass. Requested @xander-l review by comment. This is partial delivery: transport, backend admission, baseline/publication and remaining #477 gates stay open.
````

<a id="issue-478"></a>

### #478: Economy accounting [04/16]: persist accounting evidence atomically in flat-file mode

- Issue: https://github.com/Community-Duris/Duris/issues/478
- Opened by `xander-l` on 2026-09-17
- Labels: `enhancement`, `area:database`, `status:blocked`, `priority:P2`, `area:economy`
- Discussion created: #648 (Ideas)

````markdown
Parent: #474

**Slice:** 04/16 · **Priority:** P2 · **Readiness:** blocked

**Merge prerequisites:** #477

Flat-file authority currently carries bounded domain receipts and recoverable after-images. Full accounting needs retained movement evidence without exposing one-sided files, losing replay identity, or growing a per-player file without bound.

## Scope

- Implement the slice 02 adapter using flatfile_authority_transaction. Commit accounting evidence, affected domain after-images and exact operation result under the same durable recovery protocol.
- Define versioned, checksummed, bounded accounting storage with indexes/segments or an equivalent bounded format. Include a durable operation lookup sufficient for retries after reconnect, copyover and restart.
- Coordinate journal durability, fsync/rename/directory durability, recovery and failure classification with the existing authority lock. Stage large item batches without exceeding the transaction operation-count or byte limits.
- Specify rotation and compaction boundaries that retain baseline/checkpoint evidence and replay protection. Fail visibly at capacity; do not prune required evidence or silently disable accounting.
- Register every new durable file class in the lifecycle/backup inventory as part of this change. Serially coordinate shared manifests after slice 03; separate new backend files can be implemented against slice 02 fixtures.

## Acceptance criteria

- [ ] Crashes at every publication boundary recover either the prior state or the complete committed state, with no orphaned domain effect or posting.
- [ ] Restarted replay of a committed operation returns its original result and cannot reapply value, including operations older than a hot in-memory receipt cache.
- [ ] Corrupt/truncated/unsupported journals and storage exhaustion block affected operations with a recoverable diagnostic; they do not acknowledge success.
- [ ] SQL and flat-file fixtures produce equivalent canonical accounting output and errors. Per-operation work and recovery memory have explicit bounds.

## Validation

Executable flat-file harnesses inject short writes, fsync/rename failures, process termination, stale files, corruption, full capacity, replay and maximum batches. Compare canonical results against the shared golden fixtures; run lifecycle and backup inventory checks.

## File ownership and interfaces

Own new flat-file accounting storage and minimal transaction integration. Merge shared manifest/build edits after slice 03 to avoid parallel numbering/registry changes.

## Working agreement

- Read current master and AGENTS.md before implementation; the source baseline below is a planning reference, not a production-validation claim.
- One implementation owner per slice. Claim the issue and owned files before editing; use one cohesive PR or explicitly linked small PRs. Do not assign an invented GitHub user.
- Respect the parent tracker’s shared-file handoffs. Allocate immutable migration numbers on current master at merge; never rewrite sealed migration history. Register durable stores with compatibility/lifecycle changes in the same PR.
- Every behavior change includes meaningful executable regression coverage and the relevant supported-backend journey. Run touched-line formatting and make -C src for C/C++ changes; report exact commands, results and any unavailable checks.
- Preserve exact operation IDs, existing unresolved-receipt fences and post-commit publication. Tests of one persistence mode do not establish support in the other.
- Update the writer coverage inventory, related reconciliation adapters and dependent readiness labels when the slice lands. A missing integration stays blocked rather than becoming an undocumented fallback.
- Use synthetic/redacted fixtures; keep credentials, player identities, raw UIDs from live data and private recovery evidence out of public issues. Production migration/deployment or instance restitution requires separate owner authorization.

## Source references

Planning baseline: `21121ef7d80a6476d2effc601e28178a72021572`. Verify drift before implementation. New paths named in scope are proposed deliverables, not existing files.

- [src/flatfile/flatfile_authority_transaction.h](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/flatfile/flatfile_authority_transaction.h)
- [src/flatfile/flatfile_authority_transaction.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/flatfile/flatfile_authority_transaction.c)
- [src/flatfile/flatfile_player_domain_repository.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/flatfile/flatfile_player_domain_repository.c)
- [src/flatfile/flatfile_item_repository.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/flatfile/flatfile_item_repository.c)
- [tests/async/flatfile_authority_transaction_harness.cpp](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/tests/async/flatfile_authority_transaction_harness.cpp)

<!-- economy-accounting-2026-09-17:04 -->
````

#### Comment 1 of 9: `RGitGoin`, 2026-09-18

https://github.com/Community-Duris/Duris/issues/478#issuecomment-5732212734

````markdown
Claiming implementation ownership under the authorized full #474 effort for the flatfile authority/accounting integration and retained replay work. Work is isolated on `codex/474-economy-accounting`. This remains incomplete and dependent on the preceding contract/API work; no readiness or validation claim is implied. The full effort will be submitted as one final PR for `xander-l` review.
````

#### Comment 2 of 9: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/478#issuecomment-5766105665

````markdown
Claiming the next linked #474 increment: bounded flat-file accounting evidence storage and its authority-journal integration, reusing preserved 42cdf47c1 after checking later correctness fixes. Owned paths: flatfile_accounting_store, narrow flatfile authority/read/provisioning changes, build registration, lifecycle/backup registration and focused storage/fault tests. This storage prerequisite does not activate gameplay or claim completion of #478; retained lifetime metadata and typed bank owner follow with their own qualification.
````

#### Comment 3 of 9: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/478#issuecomment-5766292728

````markdown
Ownership update: draft PR #605 delivers bounded retained accounting evidence and the private authority-journal bridge, with selected later durability fixes. Current receipts retain failure stage and4096 result bytes; indexes/segments are lifecycle/backup registered. All85 original storage fault cases plus new hardening regressions pass under sanitizers; both full builds pass. @xander-l review requested by comment. #478 remains open: retained lifetime/epoch metadata, typed bank ownership, semantic restore and complete backend journeys still require delivery.
````

#### Comment 4 of 9: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/478#issuecomment-5766360361

````markdown
Continuing ownership with the next linked increment: retained flat-file lineage, epoch and lifetime metadata atop #605, reusing6698326e4 with required correctness fixes. Owned paths: flatfile_accounting_authority, its narrow storage lookup helper, lifecycle/backup/build registration and focused authority tests/docs. No gameplay activation or baseline tooling is introduced; the typed bank owner follows after this authority prerequisite.
````

#### Comment 5 of 9: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/478#issuecomment-5766542563

````markdown
Ownership update: draft #606 adds retained flat-file lineage, epoch and wallet/shared-bank lifetime metadata atop #605. Native authority/storage sanitizer suites, both builds and lifecycle/backup checks pass. Historical epoch lookup and allocation-failure classification are included; gameplay and native lifecycle changes remain inactive. @xander-l review requested by comment. Next: borrowed-lock native reads and the typed flat-file bank owner, with current receipt-stage checks. #478 remains open.
````

#### Comment 6 of 9: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/478#issuecomment-5766560992

````markdown
Continuing ownership with typed flat-file bank transactions atop #606. This linked increment reuses borrowed-lock native reads from 42cacc40e and the standalone bank owner from d47c7af0b. Owned paths: identity/domain borrowed reads, private prepared currency writer, bank transaction owner, build/docs and native-read/bank tests. Preserve DURECR2 failure-stage checks, current accounting results and independent legacy receipt limits. Gameplay/backend admission and baseline activation remain separate gates.
````

#### Comment 7 of 9: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/478#issuecomment-5766741485

````markdown
Phased delivery update: draft PR #607 adds the standalone typed flat-file bank owner on #606, at 7906655852d624dbda598aa1afae357c1fba8381. Ownership claim was posted before implementation. @xander-l review requested by PR comment.

Local verification passed: both native ASan/UBSan suites, 608 bank allocation failures including 224 during/after commit, journal-only and four image crash boundaries, forged evidence, retained replay and contention; existing identity/domain regressions; 26 contracts/census/formatting; full flat-file and MariaDB builds. Hosted CI remains pending.

Next deliverable is bank-only flat-file backend dispatch/admission. Gameplay, maintenance baseline, lifecycle ownership, other writer coverage and final qualification remain open. This component does not close #478 or any other #474 child issue and does not activate production accounting.
````

#### Comment 8 of 9: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/478#issuecomment-5766760102

````markdown
Continuing the claimed #474 work with the next linked #478 deliverable: bank-only flat-file dispatcher and coordinator admission, based on #607. Reuse the existing typed validator and transaction owner; verify durable coordinator replay against native flat-file storage. Other schema-2 roots, gameplay producers, baseline and activation remain separate pending work.
````

#### Comment 9 of 9: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/478#issuecomment-5766981806

````markdown
Next linked deliverable published: draft PR #608 at 190602263f0249b4859981ab7733e14bb469f5e4, based on #607, connects flat-file bank dispatch and admission. @xander-l review requested by comment.

Native sanitizer tests prove exact original-ID/timestamp replay with one balance mutation, fresh acknowledgement retirement and unsupported durable-work refusal. Existing admission/default-gate tests, census/formatting, both full builds and disposable flat-file boot passed. Hosted CI pending.

The native journey exposed replay auto-retirement without restored publication retention. This is tracked explicitly as required bank gameplay recovery work before activation, not claimed fixed. Committed bank balances reload from native authority; no lost-balance finding is established here.

Next reusable component: pure baseline preparation and source-witness codecs, followed by native baseline/enrollment and the required maintenance/publication boundary. All #474 child issues remain open; this does not activate accounting or complete a player journey.
````

<a id="issue-479"></a>

### #479: Economy accounting [05/16]: establish opening balances and a restart-safe cutover

- Issue: https://github.com/Community-Duris/Duris/issues/479
- Opened by `xander-l` on 2026-09-17
- Labels: `enhancement`, `area:database`, `status:blocked`, `priority:P2`, `area:economy`
- Discussion created: #649 (Ideas)

````markdown
Parent: #474

**Slice:** 05/16 · **Priority:** P2 · **Readiness:** blocked

**Merge prerequisites:** #477, #478

Existing balances and item custody predate the new journal. Enabling accounting without an honest cutover would either invent history, double count retained operations, or miss value in pending auction claims and in-flight commands.

## Scope

- Build read-only preflight and resumable baseline tooling for both backends. Use an approved quiesced boundary or a proven consistent revision boundary after resolving/draining in-flight and unpublished operations.
- Record an accounting epoch, exact source revisions, covered domains, and balanced opening entries against a designated opening-equity account. Include wallet/bank, physical piles, auction escrow/pending claims and other inventory-defined holdings exactly once.
- Baseline item UID, current custody, state and root/parent topology without issuing new UIDs or reclassifying restore as creation. Keep unknown/quarantined historical evidence explicit.
- Add per-domain coverage state and boot compatibility gates. New adapters can be deployed before activation, but each domain activates with a fresh exact boundary so intervening legacy writes are not hidden.
- Persist activation progress and hashes; retry a partially completed preparation without duplicate openings. Refuse old binaries or writers that cannot honor an activated epoch.
- Supply disposable rehearsal, dry-run output, validation, safe deactivation/pause and recovery instructions. After activation, rollback must retain operation evidence and replay protection rather than revert to an unjournaled writer.

## Acceptance criteria

- [ ] Before/after baseline rehearsal leaves all gameplay balances, item UIDs and ownership unchanged while the accounting opening totals reconcile.
- [ ] Pending claims and active escrow are included without duplicating already credited wallets; shared account banks and pile contents are counted once.
- [ ] Interrupted/repeated baseline and activation produce exactly one opening per account/epoch and no coverage gap.
- [ ] Blocked/ambiguous operations, contradictory baselines, unsupported old writers or unresolved custody discrepancies fail preflight with actionable evidence.

## Validation

Test populated and empty SQL/flat-file fixtures, shared banks, nested coin piles, live and ended auctions, offline claims, legacy receipts, quarantines and interruption at each cutover stage. Validate both fresh installs and upgrades; production execution remains separately owner-authorized.

## File ownership and interfaces

Own baseline/activation tools and accounting coverage registry integration. Work with slices 06–12 for actual domain activation boundaries and slice 15 for lifecycle/restore rules.

## Working agreement

- Read current master and AGENTS.md before implementation; the source baseline below is a planning reference, not a production-validation claim.
- One implementation owner per slice. Claim the issue and owned files before editing; use one cohesive PR or explicitly linked small PRs. Do not assign an invented GitHub user.
- Respect the parent tracker’s shared-file handoffs. Allocate immutable migration numbers on current master at merge; never rewrite sealed migration history. Register durable stores with compatibility/lifecycle changes in the same PR.
- Every behavior change includes meaningful executable regression coverage and the relevant supported-backend journey. Run touched-line formatting and make -C src for C/C++ changes; report exact commands, results and any unavailable checks.
- Preserve exact operation IDs, existing unresolved-receipt fences and post-commit publication. Tests of one persistence mode do not establish support in the other.
- Update the writer coverage inventory, related reconciliation adapters and dependent readiness labels when the slice lands. A missing integration stays blocked rather than becoming an undocumented fallback.
- Use synthetic/redacted fixtures; keep credentials, player identities, raw UIDs from live data and private recovery evidence out of public issues. Production migration/deployment or instance restitution requires separate owner authorization.

## Source references

Planning baseline: `21121ef7d80a6476d2effc601e28178a72021572`. Verify drift before implementation. New paths named in scope are proposed deliverables, not existing files.

- [migrations/baseline_currency_balances.sh](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/migrations/baseline_currency_balances.sh)
- [migrations/reconcile_currency_balances.sh](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/migrations/reconcile_currency_balances.sh)
- [migrations/item_ownership_ledger.sql](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/migrations/item_ownership_ledger.sql)
- [docs/persistence/IMMUTABLE_MIGRATIONS.md](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/docs/persistence/IMMUTABLE_MIGRATIONS.md)
- [docs/persistence/RUNTIME_COMPATIBILITY.md](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/docs/persistence/RUNTIME_COMPATIBILITY.md)

<!-- economy-accounting-2026-09-17:05 -->
````

#### Comment 1 of 10: `RGitGoin`, 2026-09-18

https://github.com/Community-Duris/Duris/issues/479#issuecomment-5734839034

````markdown
Implementation ownership claim for #479 as part of the authorized single final PR for #474, with review requested from xander-l when the complete implementation is ready.

Current upstream was reverified at `440248b17eecc3517229a48a4946cf6c0a33ffa5`. Work remains isolated on `codex/474-economy-accounting`; the SQL and flatfile foundations are local checkpoints, not merged prerequisites or completed slices.

I own the baseline/activation tooling and coverage registry integration, starting with durable lineage/epoch and nonreused wallet/bank mapping metadata needed by the typed adapters. This includes new accounting lifecycle/flatfile authority modules, focused synthetic rehearsal tests, and serial changes to the accounting storage, build and lifecycle registrations already owned under #477/#478. Existing identity, player-domain and account repository seams will be changed only where required to derive locked native identity and actual effects.

Activation remains closed until consistent boundaries, retained replay, all required domain adapters and the full qualification matrix are in place. Missing history will not be treated as a fresh baseline. This claim does not authorize any production migration, baseline, activation or gameplay operation.
````

#### Comment 2 of 10: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/479#issuecomment-5766999786

````markdown
Continuing #474 with a linked #479 preparation component based on #608: pure balanced baseline adapter, canonical complete source-witness codec and command binding, reusing 5c7d0683c / 53fd01af9 / dac52b03f. Owned scope includes those economy modules and focused tests, narrow plan/intent/envelope support, build registration and contract documentation. Baseline execution, source capture, maintenance ownership, publication recovery and activation remain closed/pending.
````

#### Comment 3 of 10: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/479#issuecomment-5767199408

````markdown
Linked baseline preparation deliverable published as draft PR #609 at 5fd726388e453c7e08d95b480b0c04c928e405f6, based on #608. Ownership was claimed before edits; @xander-l review requested by PR comment.

Both SQL/client-free ASan/UBSan suites passed independent witness/payload references, canonical/malformed/max-size cases, native revision preservation and allocation sweeps. Real coordinator refusal proves baseline commands cannot execute or checkpoint. Existing plan/intent goldens, bank admission, mixed-journal refusal, 26 contracts, census/formatting and both full server builds passed. Hosted CI pending.

This is pure preparation and command binding. Native source capture, baseline persistence, maintenance cutover ownership, publication/save recovery and activation remain open. Next linked component is flat-file baseline witness/reservation storage, with lifecycle/backup registration and current journal/failure-stage compatibility. No #474 child issue is closed and no production operation is authorized by this PR.
````

#### Comment 4 of 10: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/479#issuecomment-5767211811

````markdown
Continuing #474 / #479 with linked flat-file baseline storage on #609: retain complete witnesses and per-epoch opening reservations, register all three lifecycle/backup file classes, and qualify crash/retry behavior. Reuse ad840cf4c adapted to current v2 journal framing and DURECR2 failure-stage checks. Owned scope is the baseline storage module, its narrow private-store bridge, registration/docs and focused tests. No SQL migration, gameplay adapter, baseline admission or activation is included.
````

#### Comment 5 of 10: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/479#issuecomment-5767381437

````markdown
Linked flat-file baseline storage is published as draft PR #610 at a039c6c9446b01c8262fdc6b44354f8f82a20627, based on #609. @xander-l review requested by comment.

Local qualification passed: 41 native restart boundaries, 606 staging and 419 lookup allocation failures, duplicate/replay/epoch/max-witness cases, failure-stage tamper/hardlink/pending-journal refusal; shared storage85 fault cases; lifecycle11, backup4, contracts26, census/formatting; full flat-file and MariaDB builds. Hosted CI pending.

Lifecycle registration includes all three baseline classes and their previously unregistered existing v2 transaction-journal dependency. No new journal format, production lifecycle owner, baseline admission or activation is added.

Next deliverable: SQL baseline schema and private transaction owner, with fresh migration/runtime fingerprints and native engine verification. Source capture/enrollment, maintenance cutover, publication/save acknowledgement and all remaining coverage remain open. No #474 child issue is closed by this component.
````

#### Comment 6 of 10: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/479#issuecomment-5767396688

````markdown
Continuing #474 / #479 with linked SQL baseline schema and private transaction owner on #610, reusing e52e18003 and 2c2469cff. Current master remains 48c0aedd8; provisional new migration0032 follows this stack's accounting0031 without editing sealed migrations. Owned scope includes three baseline tables, schema/runtime verification and lifecycle registration, transaction helper and native tests. Fresh disposable MySQL/MariaDB fingerprints, upgrade/replay and fault tests are required. Source capture/enrollment, lifecycle admission, maintenance cutover and activation remain pending.
````

#### Comment 7 of 10: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/479#issuecomment-5767783367

````markdown
Published the next phased component: PR #612 at dab03b0e6cbb8d8bf47992313c26c24c02455977, following #610. It adds private SQL baseline witness retention and per-epoch identity reservations, migration0032 and lifecycle/runtime registration. Fresh installs, actual0031 upgrades, schema enforcement, native transaction faults and 50 MariaDB concurrency rounds passed. The concurrency test now handles proven1213 deadlock victims with bounded fresh-session original-ID retry; production locking is unchanged.

This is storage-component progress, not completion of #479 or gameplay activation. Next are authenticated native source capture and wallet/shared-bank enrollment, then maintenance cutover ownership and restart-safe publication/save acknowledgement for the first complete journey. All16 child issues remain open; no production migration/deployment occurred. @xander-l review requested on the linked PR.
````

#### Comment 8 of 10: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/479#issuecomment-5767815532

````markdown
Continuing ownership of #479's next linked component after PR #612: bounded read-only SQL source capture and typed normalization, reused from ecfee1218/f96949f7f and checked against current master/stack. Own new economic_sql_source_snapshot and economic_sql_source_normalize modules, their focused tests, Makefile registration and component docs in codex/474-phase13-sql-source. This phase retains exact native evidence and explicit contradictions; it does not enroll lifetimes or authorize activation. Native enrollment and the maintenance/publication boundary follow. No production source capture, migration or gameplay interaction will occur.
````

#### Comment 9 of 10: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/479#issuecomment-5767962556

````markdown
Published the next phased component, PR #613 at 084bdc3ce130377cc22b395c4155586cbcae0ba8, following #612. It captures 18 selected native SQL sources under one bounded read-only snapshot and normalizes money/custody evidence with explicit unresolved diagnostics. It changes no native balances, UIDs, custody or schema.

MySQL/MariaDB ASan/UBSan suites passed 58 query faults, 107 capture allocation faults and 125 normalization allocation faults per engine, plus snapshot/DDL/session/capacity/disconnect/lost-ACK fixtures and client-free checks. Both full server builds and 26 contract tests passed. Writer coverage remains unchanged; no child-issue completion is claimed.

The next wallet/shared-bank enrollment component can use this capture directly without importing the later physical/auction/collector expansions. Real lifecycle ownership, authorization, a retained maintenance boundary and restart-safe publication/save acknowledgement still remain before the first complete gameplay journey. @xander-l review requested. No production capture or deployment occurred.
````

#### Comment 10 of 10: `RGitGoin`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/479#issuecomment-5768000128

````markdown
Continuing #479 ownership with the next linked component after PR #613: initial SQL wallet/shared-bank lifetime enrollment and its source-capture-to-baseline integration. Worktree codex/474-phase14-sql-enrollment owns the enrollment command/transaction modules, borrowed wallet/bank source verifier, structural type registration, tests and docs. Reuse be31d953 against the current 18-table capture; no broader physical/auction/collector import or migration is planned. Test the captured account-name field explicitly; do not claim uncaptured character-name/generation provenance. Real lifecycle authorization, maintenance ownership and publication acknowledgement remain required before activation. No production migration/capture/deployment.
````

<a id="issue-480"></a>

### #480: Economy accounting [06/16]: journal wallet, bank and physical coin transfers

- Issue: https://github.com/Community-Duris/Duris/issues/480
- Opened by `xander-l` on 2026-09-17
- Labels: `enhancement`, `area:database`, `status:blocked`, `priority:P2`, `area:items`, `area:economy`
- Discussion created: #650 (Ideas)

````markdown
Parent: #474

**Slice:** 06/16 · **Priority:** P2 · **Readiness:** blocked

**Merge prerequisites:** #479

Existing two-endpoint coin transfers conserve value, but wallet, bank and pile movements need uniform durable postings and root-operation links before reconciliation can cover them together.

## Scope

- Integrate accounting plans with currency_command, coin_transfer_command and currency_transaction for give/get/drop/put, bank deposit/withdrawal, supported splits and other pure currency moves identified by the inventory.
- Record wallet, account/racewar bank and pile-UID counterparts from exact authoritative before/after state. Preserve denomination vectors, making change, partial pickup, pile merge/split and pile destruction/creation evidence.
- Keep compound currency children inside one existing authority commit; parent and child relationships must be queryable without reverse-engineering an ID hash.
- Maintain post-commit publication, shared-bank fences, deferred source/destination revalidation and exact receipt retention. No timeout refund or replacement ID after an ambiguous commit.
- Preserve existing bulk-command semantics: each accepted subtransfer has a complete operation, while commands that promise one atomic exchange retain a single boundary. Accounting must not quietly make get-all globally atomic.

## Acceptance criteria

- [ ] Every successful covered transfer has zero net coin-value change, matching actual balances/pile payload, with no duplicate counting of the pile object.
- [ ] Insufficient funds, overflow, stale ownership/revision, moved containers and rejected destination publication cannot commit half a transfer or report false success.
- [ ] Same-account participants sharing a bank, linkdead/reconnect and concurrent debits retain existing correctness.
- [ ] Replay and reload retain denominations, container weights and item/room projections without another currency posting.

## Validation

Extend existing currency and coin SQL/flat-file harnesses plus real disposable player journeys for give, deposit/withdraw, partial/full get/put/drop, pile merge, group split and nested containers. Inject failure before/after each endpoint and after commit before publication; include existing area-authored ITEM_MONEY coverage.

## File ownership and interfaces

Own generic currency/coin gameplay integration. Shared SQL/flat-file transaction helpers remain owned by 03/04; specialized economy writers are assigned to later slices.

## Working agreement

- Read current master and AGENTS.md before implementation; the source baseline below is a planning reference, not a production-validation claim.
- One implementation owner per slice. Claim the issue and owned files before editing; use one cohesive PR or explicitly linked small PRs. Do not assign an invented GitHub user.
- Respect the parent tracker’s shared-file handoffs. Allocate immutable migration numbers on current master at merge; never rewrite sealed migration history. Register durable stores with compatibility/lifecycle changes in the same PR.
- Every behavior change includes meaningful executable regression coverage and the relevant supported-backend journey. Run touched-line formatting and make -C src for C/C++ changes; report exact commands, results and any unavailable checks.
- Preserve exact operation IDs, existing unresolved-receipt fences and post-commit publication. Tests of one persistence mode do not establish support in the other.
- Update the writer coverage inventory, related reconciliation adapters and dependent readiness labels when the slice lands. A missing integration stays blocked rather than becoming an undocumented fallback.
- Use synthetic/redacted fixtures; keep credentials, player identities, raw UIDs from live data and private recovery evidence out of public issues. Production migration/deployment or instance restitution requires separate owner authorization.

## Source references

Planning baseline: `21121ef7d80a6476d2effc601e28178a72021572`. Verify drift before implementation. New paths named in scope are proposed deliverables, not existing files.

- [src/economy/coin_transfer_command.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/coin_transfer_command.c)
- [src/economy/currency_transaction.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/currency_transaction.c)
- [src/persistence/critical_command_repository.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/persistence/critical_command_repository.c)
- [tests/async/currency_transaction_mysql_harness.cpp](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/tests/async/currency_transaction_mysql_harness.cpp)
- [tests/async/test_coin_custody_lifecycle.py](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/tests/async/test_coin_custody_lifecycle.py)
- [tests/async/test_currency_input_queue.py](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/tests/async/test_currency_input_queue.py)

<!-- economy-accounting-2026-09-17:06 -->
````

#### Comment 1 of 1: `RGitGoin`, 2026-09-18

https://github.com/Community-Duris/Duris/issues/480#issuecomment-5732545668

````markdown
Claiming #480 under the authorized full #474 implementation. I own generic currency/coin integration and its tests, beginning with typed currency preparation in `currency_command` and a bank-transfer accounting adapter. Shared SQL/flatfile transaction helpers remain coordinated under the existing #477/#478 claims. This is incomplete work on `codex/474-economy-accounting`; prerequisite activation/storage and backend qualification are still outstanding. One final PR will cover the full effort for `xander-l` review.
````

<a id="issue-481"></a>

### #481: Economy accounting [07/16]: account for coin issuance, expenses and authorized adjustments

- Issue: https://github.com/Community-Duris/Duris/issues/481
- Opened by `xander-l` on 2026-09-17
- Labels: `enhancement`, `area:database`, `status:blocked`, `priority:P2`, `area:economy`
- Discussion created: #651 (Ideas)

````markdown
Parent: #474

**Slice:** 07/16 · **Priority:** P2 · **Readiness:** blocked

**Merge prerequisites:** #480

A wallet reward or payment is legitimate only when its new or removed value has an explicit authorized counterpart. Generic positive/negative deltas cannot establish economy-wide issuance and sink totals.

## Scope

- Use the slice 01 inventory to route quest/NPC rewards, starter/chaos grants, boons, service costs, locker identification, ship/cargo/insurance/guild/kingdom costs where present, refunds and administrator adjustments through named counterpart policies.
- Identify whether each producer spends a real durable balance or issues currency and whether each consumer holds proceeds or destroys value. Preserve existing mechanics; adding accounting must not impose a new finite NPC treasury or change prices.
- Record lifecycle-scoped source identifiers for issuance and stable refund/correction references. Restoration and retrieval of previously held value must never be mislabeled as a reward.
- Require typed authority for mint/sink/operator reasons; normal gameplay cannot request arbitrary system balancing entries. Supply bounded diagnostics for remaining direct writes and fail closed on an activated writer bypass.
- Keep currency-bearing combat/death compound writers for slice 12 and specialized commercial writers for 09–11; the inventory must reflect these boundaries.

## Acceptance criteria

- [ ] Each covered issuance/expense has one explicit authorized counter-entry, and replay produces no additional reward, charge or refund.
- [ ] Transfers, refunds, openings and administrative corrections are distinguishable from new rewards in gross/net supply reports.
- [ ] Wrong sign, unapproved reason/source pairing, invalid grant identity and bypass attempts are rejected even when numeric entries balance.
- [ ] All current generic currency reasons have an explicit policy and fixture or a documented not-applicable route; there is no catch-all balancing account.

## Validation

Executable policy tests and both-backend player journeys cover representative reward, expense, partial denomination payment, refund, starter replay and administrator authorization. Test delayed publication, insufficient funds, repeated source events and malicious/malformed internal plans.

## File ownership and interfaces

Own issuance/sink policy implementations and generic economic call sites from the inventory. Do not change existing prices, reward amounts, combat outcomes or telemetry transport.

## Working agreement

- Read current master and AGENTS.md before implementation; the source baseline below is a planning reference, not a production-validation claim.
- One implementation owner per slice. Claim the issue and owned files before editing; use one cohesive PR or explicitly linked small PRs. Do not assign an invented GitHub user.
- Respect the parent tracker’s shared-file handoffs. Allocate immutable migration numbers on current master at merge; never rewrite sealed migration history. Register durable stores with compatibility/lifecycle changes in the same PR.
- Every behavior change includes meaningful executable regression coverage and the relevant supported-backend journey. Run touched-line formatting and make -C src for C/C++ changes; report exact commands, results and any unavailable checks.
- Preserve exact operation IDs, existing unresolved-receipt fences and post-commit publication. Tests of one persistence mode do not establish support in the other.
- Update the writer coverage inventory, related reconciliation adapters and dependent readiness labels when the slice lands. A missing integration stays blocked rather than becoming an undocumented fallback.
- Use synthetic/redacted fixtures; keep credentials, player identities, raw UIDs from live data and private recovery evidence out of public issues. Production migration/deployment or instance restitution requires separate owner authorization.

## Source references

Planning baseline: `21121ef7d80a6476d2effc601e28178a72021572`. Verify drift before implementation. New paths named in scope are proposed deliverables, not existing files.

- [src/economy/currency_command.h](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/currency_command.h)
- [src/economy/currency_transaction.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/currency_transaction.c)
- [src/economy/boon.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/boon.c)
- [src/item/locker_identify.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/item/locker_identify.c)

<!-- economy-accounting-2026-09-17:07 -->
````

<a id="issue-482"></a>

### #482: Economy accounting [08/16]: link item custody and lifecycle events to economic operations

- Issue: https://github.com/Community-Duris/Duris/issues/482
- Opened by `xander-l` on 2026-09-17
- Labels: `enhancement`, `area:database`, `status:blocked`, `priority:P2`, `area:items`, `area:economy`
- Discussion created: #652 (Ideas)

````markdown
Parent: #474

**Slice:** 08/16 · **Priority:** P2 · **Readiness:** blocked

**Merge prerequisites:** #479

The current item ledger records both owners, but full audit reconstruction also needs compound-operation links, creation/destruction semantics and before/after topology for moves within the same owner.

## Scope

- Reuse item_current_owner and item_ownership_ledger as custody authority. Link their immutable events to the accounting operation and expose normalized source/destination audit views rather than create a competing ownership balance table.
- Preserve prior and resulting root/parent topology where existing evidence only stores the resulting topology. Add versioned additive evidence as required, serially updating schema/compatibility manifests.
- Integrate ordinary player/container/room/locker/equipment moves and supported pet/mobile routes through their current authority. Retain explicit refusal where durable NPC custody is unsupported; do not invent a valid owner for a live-only object.
- Represent supported fresh creation, first durable admission, crafting/transformation, consumption, decay/destruction and operator repair explicitly per UID. Preserve existing artifact/unique-item, binding, consent and eligibility rules.
- Record whole-container movement without multiplying descendant currency value; distinguish pile custody from changes to its monetary content. Preserve current bounded batch and partial-command behavior.

## Acceptance criteria

- [ ] Every admitted active UID has one valid custodian and acyclic complete topology; creation/destruction/transfer can be reconstructed without counting a VNUM as identity.
- [ ] Same-owner bag/inventory moves produce correct history and no false no-op rejection. Nested contents, equipment and multi-root batches retain exact identity and metadata.
- [ ] Stale owner, duplicate UID, invalid parent, over-limit batch and unauthorized creation/destruction reject without partial movement.
- [ ] SQL and flat-file replay, reconnect and restart preserve custody and accounting references. Unsupported routes remain explicitly unsupported.

## Validation

Extend item transfer/custody harnesses with topology history, container trees, same-owner moves, creation/destruction, stale parents, duplicate replay and boundary batch sizes. Exercise supported player/pet journeys against both backends and coordinate known failures with #467, #471 and #473 without folding their investigations into this feature.

## File ownership and interfaces

Own generic item event integration and topology evidence. Death/world orchestration remains slice 12; shop, collector and auction adapters remain slices 09–11. Existing defect owners retain their fixes.

## Working agreement

- Read current master and AGENTS.md before implementation; the source baseline below is a planning reference, not a production-validation claim.
- One implementation owner per slice. Claim the issue and owned files before editing; use one cohesive PR or explicitly linked small PRs. Do not assign an invented GitHub user.
- Respect the parent tracker’s shared-file handoffs. Allocate immutable migration numbers on current master at merge; never rewrite sealed migration history. Register durable stores with compatibility/lifecycle changes in the same PR.
- Every behavior change includes meaningful executable regression coverage and the relevant supported-backend journey. Run touched-line formatting and make -C src for C/C++ changes; report exact commands, results and any unavailable checks.
- Preserve exact operation IDs, existing unresolved-receipt fences and post-commit publication. Tests of one persistence mode do not establish support in the other.
- Update the writer coverage inventory, related reconciliation adapters and dependent readiness labels when the slice lands. A missing integration stays blocked rather than becoming an undocumented fallback.
- Use synthetic/redacted fixtures; keep credentials, player identities, raw UIDs from live data and private recovery evidence out of public issues. Production migration/deployment or instance restitution requires separate owner authorization.

## Source references

Planning baseline: `21121ef7d80a6476d2effc601e28178a72021572`. Verify drift before implementation. New paths named in scope are proposed deliverables, not existing files.

- [src/item/item_transfer_repository.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/item/item_transfer_repository.c)
- [src/item/item_movement_transaction.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/item/item_movement_transaction.c)
- [src/item/item_transfer_command.h](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/item/item_transfer_command.h)
- [src/flatfile/flatfile_item_repository.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/flatfile/flatfile_item_repository.c)
- [docs/persistence/ITEM_COMMAND_PIPELINE.md](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/docs/persistence/ITEM_COMMAND_PIPELINE.md)
- [tests/async/item_transfer_mysql_harness.cpp](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/tests/async/item_transfer_mysql_harness.cpp)

<!-- economy-accounting-2026-09-17:08 -->
````

#### Comment 1 of 1: `RGitGoin`, 2026-09-18

https://github.com/Community-Duris/Duris/issues/482#issuecomment-5732212971

````markdown
Claiming implementation ownership under the authorized full #474 effort for the item custody accounting integration, including guarded direct transaction entrypoints and the later history linkage. Work is isolated on `codex/474-economy-accounting`. This remains incomplete and dependent on the preceding contract/API work; no readiness or validation claim is implied. The full effort will be submitted as one final PR for `xander-l` review.
````

<a id="issue-483"></a>

### #483: Economy accounting [09/16]: make shop purchases and sales balanced atomic exchanges

- Issue: https://github.com/Community-Duris/Duris/issues/483
- Opened by `xander-l` on 2026-09-17
- Labels: `enhancement`, `area:database`, `status:blocked`, `priority:P2`, `area:items`, `area:economy`
- Discussion created: #653 (Ideas)

````markdown
Parent: #474

**Slice:** 09/16 · **Priority:** P2 · **Readiness:** blocked

**Merge prerequisites:** #481, #482

Shop gameplay currently takes different SQL and flat-file routes. The flat-file typed shop-trade implementation cannot be assumed to prove SQL parity or atomic money/item accounting.

## Scope

- Trace both live shop buy/sell routes in shop.c and move the SQL legacy route onto an appropriate typed atomic shop repository where necessary; reuse current shop_trade contracts rather than add an independent payment path.
- For each buy-existing, buy-produced, sell-store, sell-destroy and invalid-stock cleanup action, commit the exact coin postings, item custody/lifecycle changes, stock/revision changes, and receipt together.
- Model the shop counterpart according to existing economics: retained treasury versus explicit source/sink. Produced stock must allocate a new UID exactly once, and sale-to-destruction must preserve a tombstone/event.
- Retain current prices, trophy/stock restrictions, containers, quantities, keeper disappearance behavior and eligibility; stage live publication and success messages after durable commitment.
- Update writer inventory/backend support and activation gates so neither backend can claim the slice complete through tests of the other route.

## Acceptance criteria

- [ ] A failed item delivery cannot leave a committed charge, and a failed charge cannot hand out an item; the complete trade is one balanced operation.
- [ ] Produced-stock retry creates one instance; sell-destroy and cleanup do not invent a coin payment when none exists.
- [ ] Stale stock, keeper loss, overflow, insufficient funds and moved destination containers preserve state and truthful output.
- [ ] Real SQL and flat-file buy/sell commands exercise the new boundary and produce equivalent audit evidence.

## Validation

Add a disposable SQL shop-trade integration harness where absent, extend existing flat-file harnesses, and run player journeys for all supported actions, multi-buy partial semantics, nested stock and destination containers. Inject failures at money, custody, stock, receipt and live-publication boundaries.

## File ownership and interfaces

Own shop adapters and the needed SQL shop-trade repository integration. The shared coordinator dispatch change is a serial handoff after 06; collector/auction policy is outside this slice.

## Working agreement

- Read current master and AGENTS.md before implementation; the source baseline below is a planning reference, not a production-validation claim.
- One implementation owner per slice. Claim the issue and owned files before editing; use one cohesive PR or explicitly linked small PRs. Do not assign an invented GitHub user.
- Respect the parent tracker’s shared-file handoffs. Allocate immutable migration numbers on current master at merge; never rewrite sealed migration history. Register durable stores with compatibility/lifecycle changes in the same PR.
- Every behavior change includes meaningful executable regression coverage and the relevant supported-backend journey. Run touched-line formatting and make -C src for C/C++ changes; report exact commands, results and any unavailable checks.
- Preserve exact operation IDs, existing unresolved-receipt fences and post-commit publication. Tests of one persistence mode do not establish support in the other.
- Update the writer coverage inventory, related reconciliation adapters and dependent readiness labels when the slice lands. A missing integration stays blocked rather than becoming an undocumented fallback.
- Use synthetic/redacted fixtures; keep credentials, player identities, raw UIDs from live data and private recovery evidence out of public issues. Production migration/deployment or instance restitution requires separate owner authorization.

## Source references

Planning baseline: `21121ef7d80a6476d2effc601e28178a72021572`. Verify drift before implementation. New paths named in scope are proposed deliverables, not existing files.

- [src/economy/shop.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/shop.c)
- [src/economy/shop_trade_command.h](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/shop_trade_command.h)
- [src/economy/shop_trade_transaction.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/shop_trade_transaction.c)
- [src/flatfile/flatfile_shop_trade_repository.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/flatfile/flatfile_shop_trade_repository.c)
- [tests/async/flatfile_shop_trade_repository_harness.cpp](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/tests/async/flatfile_shop_trade_repository_harness.cpp)

<!-- economy-accounting-2026-09-17:09 -->
````

<a id="issue-484"></a>

### #484: Economy accounting [10/16]: journal collector purchases, buybacks and item expiry

- Issue: https://github.com/Community-Duris/Duris/issues/484
- Opened by `xander-l` on 2026-09-17
- Labels: `enhancement`, `area:database`, `status:blocked`, `priority:P2`, `area:items`, `area:economy`
- Discussion created: #654 (Ideas)

````markdown
Parent: #474

**Slice:** 10/16 · **Priority:** P2 · **Readiness:** blocked

**Merge prerequisites:** #481, #482

Collectors write currency and ownership records through specialized repositories. They must participate in the same balanced accounting contract without repeating death enrollment or changing beneficiary and eligibility policy.

## Scope

- Integrate collector acquisition, purchase, buyback, payout/fee handling where applicable, release and expiry using existing collector transactions in SQL and flat-file mode.
- Include money, listing state, beneficiary/claim references and item events in one parent operation. Derive treasury/source/sink behavior from current policy; account for any intermediate holding balance explicitly.
- Preserve death enrollment as linked metadata rather than a second issuance or ownership transfer; the death boundary is integrated by slice 12.
- Keep cache invalidation and notices as post-commit effects. Retried maintenance and notification must not consume or pay for a listing again.
- Update coverage inventory, lifecycle evidence and counterparty classifications for each collector action.

## Acceptance criteria

- [ ] Money and UID custody change together on purchase/buyback, and expiry is explicit item destruction or a documented transfer with no unexplained coin delta.
- [ ] Repeated purchase, sale/expiry races, stale listing, beneficiary mismatch and insufficient funds cannot duplicate value or ownership.
- [ ] Offline publication and catalog refresh never cause compensation of an already committed transaction.
- [ ] SQL and flat-file collectors produce equivalent balanced evidence for the same policy fixtures.

## Validation

Extend collector SQL/flat-file command and repository harnesses; test purchase versus expiry contention, retry after commit, offline beneficiary, death enrollment replay and actual player buyback journeys. Assert listing, wallet, item, operation links and notifications independently.

## File ownership and interfaces

Own collector repository/service integration. Shared item helpers and death lifecycle are consumed through frozen interfaces; shared schema extensions merge serially.

## Working agreement

- Read current master and AGENTS.md before implementation; the source baseline below is a planning reference, not a production-validation claim.
- One implementation owner per slice. Claim the issue and owned files before editing; use one cohesive PR or explicitly linked small PRs. Do not assign an invented GitHub user.
- Respect the parent tracker’s shared-file handoffs. Allocate immutable migration numbers on current master at merge; never rewrite sealed migration history. Register durable stores with compatibility/lifecycle changes in the same PR.
- Every behavior change includes meaningful executable regression coverage and the relevant supported-backend journey. Run touched-line formatting and make -C src for C/C++ changes; report exact commands, results and any unavailable checks.
- Preserve exact operation IDs, existing unresolved-receipt fences and post-commit publication. Tests of one persistence mode do not establish support in the other.
- Update the writer coverage inventory, related reconciliation adapters and dependent readiness labels when the slice lands. A missing integration stays blocked rather than becoming an undocumented fallback.
- Use synthetic/redacted fixtures; keep credentials, player identities, raw UIDs from live data and private recovery evidence out of public issues. Production migration/deployment or instance restitution requires separate owner authorization.

## Source references

Planning baseline: `21121ef7d80a6476d2effc601e28178a72021572`. Verify drift before implementation. New paths named in scope are proposed deliverables, not existing files.

- [src/economy/collector_repository.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/collector_repository.c)
- [src/economy/collector_transaction.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/collector_transaction.c)
- [src/economy/collector_death_enrollment.h](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/collector_death_enrollment.h)
- [src/flatfile/flatfile_collector_repository.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/flatfile/flatfile_collector_repository.c)
- [tests/async/collector_repository_mysql_harness.cpp](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/tests/async/collector_repository_mysql_harness.cpp)

<!-- economy-accounting-2026-09-17:10 -->
````

<a id="issue-485"></a>

### #485: Economy accounting [11/16]: account for auction escrow, claims, refunds and settlement

- Issue: https://github.com/Community-Duris/Duris/issues/485
- Opened by `xander-l` on 2026-09-17
- Labels: `enhancement`, `area:database`, `status:blocked`, `priority:P2`, `area:items`, `area:economy`
- Discussion created: #655 (Ideas)

````markdown
Parent: #474

**Slice:** 11/16 · **Priority:** P2 · **Readiness:** blocked

**Merge prerequisites:** #481, #482

Auction funds move through active bids and pending refund/seller claims before reaching a wallet. Accounting only the wallet delta would miss these holdings or mint value again when a claim is collected.

## Scope

- Model active auction escrow and pending money claims as explicit accounts tied to stable auction/claim identity. Preserve any existing aggregated claim storage with operation-level attribution rather than inventing unsupported row identities.
- Journal listing fees, first bids, same-bidder raises, outbid refunds into claims, buyout, timed settlement, removal/cancellation, seller proceeds/fees, item claim entitlement and final pickup.
- Move escrow to pending claims at settlement, then claims to wallets at collection; never credit a seller or refund recipient twice. Preserve current offline delivery and cancellation semantics.
- Commit auction state/revisions, money postings, item custody or claim entitlement, immutable auction ledger and root/child links atomically.
- Baseline active auctions and unclaimed proceeds/refunds through slice 05; preserve telemetry categorization so bid, settlement and pickup are not each counted as rewards.

## Acceptance criteria

- [ ] Escrow plus claims plus wallet changes reconcile through the full auction lifecycle; each amount is held in exactly one account at each stage.
- [ ] Same-bidder raises debit only the increment; outbid, canceled and failed auctions unwind the actual reserved value exactly once.
- [ ] Seller net proceeds plus fee equal the settled price, and item delivery is linked to the correct committed entitlement.
- [ ] Concurrent bid/finalize/claim, offline users, duplicate callbacks and restart yield one authoritative outcome in both storage modes.

## Validation

Extend auction SQL and flat-file harnesses with full bid-to-claim journeys, same-account constraints, multiple pending claims, rounding boundaries, competing bidders, remove/finalize races and crash injection. Assert escrow and claim balances as well as player balances. Coordinate harness changes with open PR #444.

## File ownership and interfaces

Own auction accounting and claim attribution. Preserve existing auction policy; shared migration numbering and test-harness overlap require serial handoff.

## Working agreement

- Read current master and AGENTS.md before implementation; the source baseline below is a planning reference, not a production-validation claim.
- One implementation owner per slice. Claim the issue and owned files before editing; use one cohesive PR or explicitly linked small PRs. Do not assign an invented GitHub user.
- Respect the parent tracker’s shared-file handoffs. Allocate immutable migration numbers on current master at merge; never rewrite sealed migration history. Register durable stores with compatibility/lifecycle changes in the same PR.
- Every behavior change includes meaningful executable regression coverage and the relevant supported-backend journey. Run touched-line formatting and make -C src for C/C++ changes; report exact commands, results and any unavailable checks.
- Preserve exact operation IDs, existing unresolved-receipt fences and post-commit publication. Tests of one persistence mode do not establish support in the other.
- Update the writer coverage inventory, related reconciliation adapters and dependent readiness labels when the slice lands. A missing integration stays blocked rather than becoming an undocumented fallback.
- Use synthetic/redacted fixtures; keep credentials, player identities, raw UIDs from live data and private recovery evidence out of public issues. Production migration/deployment or instance restitution requires separate owner authorization.

## Source references

Planning baseline: `21121ef7d80a6476d2effc601e28178a72021572`. Verify drift before implementation. New paths named in scope are proposed deliverables, not existing files.

- [src/economy/auction_repository.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/auction_repository.c)
- [src/economy/auction_command.h](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/auction_command.h)
- [src/economy/auction_transaction.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/economy/auction_transaction.c)
- [src/flatfile/flatfile_auction_repository.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/flatfile/flatfile_auction_repository.c)
- [tests/async/auction_transaction_mysql_harness.cpp](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/tests/async/auction_transaction_mysql_harness.cpp)

<!-- economy-accounting-2026-09-17:11 -->
````

#### Comment 1 of 1: `RGitGoin`, 2026-09-19

https://github.com/Community-Duris/Duris/issues/485#issuecomment-5739993484

````markdown
Ownership claim for the auction portion of #474. I am implementing #485 on the existing isolated `codex/474-economy-accounting` branch as part of the user's requested single final PR for xander-l.

The immediate work covers auction admission and representative-item integrity, followed by the required escrow/claim accounting and lifecycle validation. I own the auction source, focused tests, and corresponding accounting inventory/documentation changes. Existing transactional boundaries and historical evidence remain in scope; this claim does not mark the slice ready or complete.
````

<a id="issue-486"></a>

### #486: Economy accounting [12/16]: preserve accounting through death, world lifecycle and recovery

- Issue: https://github.com/Community-Duris/Duris/issues/486
- Opened by `xander-l` on 2026-09-17
- Labels: `enhancement`, `area:database`, `status:blocked`, `priority:P2`, `area:combat`, `area:world`, `area:items`, `area:economy`
- Discussion created: #656 (Ideas)

````markdown
Parent: #474

**Slice:** 12/16 · **Priority:** P2 · **Readiness:** blocked

**Merge prerequisites:** #481, #482, #469

Death, corpse creation, NPC/reset admission and recovery cross wallet, item and world boundaries. Replaying a saved object or moving coins to a corpse must not be counted as fresh issuance, and source evidence cannot be retired before durable handoff.

## Scope

- Integrate specialized combat/corpse writers with balanced parent operations: wallet to corpse/pile, item tree to corpse, loot/restore, no-corpse outcomes and existing destruction policies.
- Distinguish fresh zone/NPC/reset creation and first admission from recovered objects using stable lifecycle/generation identities. Include transient assets at the contract's declared admission boundary before they can transfer value.
- Keep extraction, purge, decay and world cleanup as explicit transfers/destruction only when gameplay actually removes an accounted asset; snapshots, hydration, copyover and reconnect are projections.
- Build on #469's restart-safe saved-item handoff rather than duplicate that fix. Retain source payload and original operation evidence until authoritative handoff is acknowledged.
- Link collector death enrollment and existing restitution operations without creating a second payout/custody event. Revalidate actual live publication and preserve unresolved receipts/fences.

## Acceptance criteria

- [ ] Death and subsequent looting preserve value except for explicitly recorded current-policy sinks, with exact UID/topology and wallet/corpse reconciliation.
- [ ] Repeated boot, copyover, NPC recovery, saved-item restore and corpse materialization add no new issuance or duplicate item event.
- [ ] Fresh reset/spawn admission occurs once per intended lifecycle; later real regeneration remains distinct and traceable.
- [ ] Crashes at source retirement, corpse commit, world materialization and publication recover deterministically. No missing/doubled payload is papered over by a balancing entry.

## Validation

Both-backend player journeys cover death with coins and nested items, corpse loot/restore, no-corpse cases, generated NPCs, reset/purge/decay, copyover and repeated saved-item recovery. Reuse #469 crash fixtures after its fix and coordinate open #467/#468/#470/#471/#473 findings as explicit test or release limitations.

## File ownership and interfaces

Own cross-domain death/world/recovery accounting adapters. #469 remains a separately owned prerequisite; this issue does not authorize instance restitution or reproduce its implementation scope.

## Working agreement

- Read current master and AGENTS.md before implementation; the source baseline below is a planning reference, not a production-validation claim.
- One implementation owner per slice. Claim the issue and owned files before editing; use one cohesive PR or explicitly linked small PRs. Do not assign an invented GitHub user.
- Respect the parent tracker’s shared-file handoffs. Allocate immutable migration numbers on current master at merge; never rewrite sealed migration history. Register durable stores with compatibility/lifecycle changes in the same PR.
- Every behavior change includes meaningful executable regression coverage and the relevant supported-backend journey. Run touched-line formatting and make -C src for C/C++ changes; report exact commands, results and any unavailable checks.
- Preserve exact operation IDs, existing unresolved-receipt fences and post-commit publication. Tests of one persistence mode do not establish support in the other.
- Update the writer coverage inventory, related reconciliation adapters and dependent readiness labels when the slice lands. A missing integration stays blocked rather than becoming an undocumented fallback.
- Use synthetic/redacted fixtures; keep credentials, player identities, raw UIDs from live data and private recovery evidence out of public issues. Production migration/deployment or instance restitution requires separate owner authorization.

## Source references

Planning baseline: `21121ef7d80a6476d2effc601e28178a72021572`. Verify drift before implementation. New paths named in scope are proposed deliverables, not existing files.

- [src/persistence/corpse_lifecycle_repository.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/persistence/corpse_lifecycle_repository.c)
- [src/combat/combat_outcome_repository.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/combat/combat_outcome_repository.c)
- [src/persistence/player_death_restitution_repository.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/persistence/player_death_restitution_repository.c)
- [src/flatfile/flatfile_corpse_repository.c](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/src/flatfile/flatfile_corpse_repository.c)
- [docs/persistence/WORLD_RECOVERY_PIPELINE.md](https://github.com/Community-Duris/Duris/blob/21121ef7d80a6476d2effc601e28178a72021572/docs/persistence/WORLD_RECOVERY_PIPELINE.md)

<!-- economy-accounting-2026-09-17:12 -->
````

<a id="issue-505"></a>

### #505: Investigate 889 main-production coin-transfer ESTALE failures (2026-09-18)

- Issue: https://github.com/Community-Duris/Duris/issues/505
- Opened by `xander-l` on 2026-09-18
- Labels: `bug`, `area:database`, `status:ready`, `priority:P1`, `type:investigation`, `area:economy`
- Discussion created: #643 (General)

````markdown
## Summary

A read-only main-production audit found a burst of **889 rejected `coin_transfer` critical-command records** (command type 17, result code 116 / Linux `ESTALE`) from **2026-09-18 03:01:58 through 04:51:51 UTC**. The count and interval match the corresponding WIZLOG `critical_command` integrity-failure alerts.

This confirms rejected coin operations in that window. It does **not** establish the initiating gameplay command, the affected source/destination revision, the root cause, or any currency loss.

## Evidence and provenance

- Evidence is aggregate-only; no player, account, item, or raw-log identifiers are included.
- The audited production checkout was [`4853b46da731bc4d12d40cad4e77b4cf123e92c5`](https://github.com/Community-Duris/Duris/tree/4853b46da731bc4d12d40cad4e77b4cf123e92c5); its [`critical_command.h`](https://github.com/Community-Duris/Duris/blob/4853b46da731bc4d12d40cad4e77b4cf123e92c5/src/persistence/critical_command.h) maps type 17 to `coin_transfer`.
- That checkout already contains auction fix [`b90e0b406`](https://github.com/Community-Duris/Duris/commit/b90e0b4061dd7a9f0063b80fd729c415f593bd19), from merged [PR #306](https://github.com/Community-Duris/Duris/pull/306), which addressed [#305](https://github.com/Community-Duris/Duris/issues/305) and publishes the source-owner revision. The audit did not independently prove that the running binary was compiled from this checkout.

## Investigation scope

1. Identify the originating command path(s) and stale revision field(s) from protected, redacted evidence.
2. Reproduce result 116 on a non-production clone or fixture and determine whether rejection occurs before any durable state mutation.
3. Compare all coin-transfer entry points with source/destination revision publication rules, including the already-merged auction fix. Do not assume #305 caused this burst or that a deployment alone resolves it.
4. Add regression coverage and a narrowly scoped fix only after the cause is established.

## Boundaries

This issue makes no currency-loss or reimbursement claim. Do not retry, compensate, reimburse, restart, deploy, or mutate production from this evidence. Any deployment, retry, or reimbursement requires separate manual authorization.
````

<a id="issue-509"></a>

### #509: Performance: cache mundane-event handles for world-activity wakeups

- Issue: https://github.com/Community-Duris/Duris/issues/509
- Opened by `xander-l` on 2026-09-19
- Labels: `enhancement`, `performance`, `status:ready`
- Discussion created: #642 (Ideas)

````markdown
Follow-up to #299. The world-activity wake path currently finds each NPC's ordinary mundane event by walking that character's complete NEVENT owner list. That makes a zone promotion pay for avoidable list traversal across every indexed NPC.

Scope:
- add a runtime-only mundane-event handle/sequence cache to `char_data`;
- record the handle at every ordinary mundane scheduling site, including the post-flee retry;
- validate the sequence, lifecycle, callback, and owner before a wake uses it;
- rebuild the cache once after boot/copyover/Redis recovery so it is never a persistence contract;
- retain the existing fallback/diagnostic behavior for stale or missing handles.

Acceptance criteria:
- activity wakeups no longer call `get_scheduled(mob, event_mob_mundane)` in the indexed hot path;
- scheduler-pool reuse and extraction cannot make a stale pointer actionable;
- cadence, combat promotion, recovery, and post-flee timing remain unchanged;
- source contracts and the available warning-profile compilation pass.
````

#### Comment 1 of 1: `xander-l`, 2026-09-19

https://github.com/Community-Duris/Duris/issues/509#issuecomment-5738548969

````markdown
Implemented in consolidated PR #511: https://github.com/Community-Duris/Duris/pull/511. This remains open until the PR is merged.
````

<a id="issue-510"></a>

### #510: Performance: remove transient allocations from PC-corpse activity traversal

- Issue: https://github.com/Community-Duris/Duris/issues/510
- Opened by `xander-l` on 2026-09-19
- Labels: `enhancement`, `performance`, `status:ready`
- Discussion created: #641 (Ideas)

````markdown
Follow-up to #299. `world_activity_object_enter/leave()` must inspect nested object trees so a PC corpse inside a carried, worn, or nested container keeps the correct zone active. The current correctness-first implementation allocates a temporary `std::unordered_set` for each non-trivial transfer even though the live containment API rejects cycles.

Scope:
- replace the per-transfer heap-backed visitor with a bounded, allocation-free tree walk;
- retain a depth fence for malformed recovery/object graphs;
- preserve PC-corpse/NPC-corpse classification, nested-container behavior, extraction, decay, and rebuild semantics;
- keep the follow-up small enough to measure independently from a future maintained subtree-count cache.

Acceptance criteria:
- ordinary object moves do not allocate a temporary hash set for corpse publication;
- malformed containment remains bounded and cannot recurse without limit;
- corpse reason counts and wake behavior remain unchanged for room, inventory, equipment, nested, recovery, and extraction paths;
- source contracts, warning-profile compilation, and diff checks pass.
````

#### Comment 1 of 1: `xander-l`, 2026-09-19

https://github.com/Community-Duris/Duris/issues/510#issuecomment-5738549066

````markdown
Implemented in consolidated PR #511: https://github.com/Community-Duris/Duris/pull/511. This remains open until the PR is merged.
````

<a id="issue-526"></a>

### #526: Add guarded exact-UID recovery for active custody with missing player payloads

- Issue: https://github.com/Community-Duris/Duris/issues/526
- Opened by `xander-l` on 2026-09-20
- Labels: `enhancement`
- Discussion created: #640 (Ideas)

````markdown
## Gap demonstrated by a completed targeted recovery

An item-loss incident left active, unambiguous player custody rows but no physical payload for a container and its descendants. The original UIDs and complete historical item metadata existed in a verified backup. Repair required a one-off, explicitly authorized stopped-writer transaction with exact UID/topology/revision guards, preserved auxiliary metadata, independent readback and rollback rehearsal.

Turn that repeatable recovery procedure into a maintained, tested operator workflow. This does **not** prevent the initiating command defects by itself; prevention is tracked in #523 and #524.

## Existing tools are different products

- #125 / merged #136 provide topology classification; the guarded nesting repair is not a generic production missing-payload restorer.
- #126 / merged #137 address ambiguous legacy import/quarantine evidence and possible UID collisions. Do not broaden that incident-specific planner silently or infer ownership from a historical UID collision.
- #331 / #375 and merged #443 / #512 provide evidence-bound **death restitution**. Missing ordinary inventory payload with active player custody is not automatically a death-restitution case. Do not fabricate death evidence or a restitution classification to make a payload fit that validator.
- Merged #495 covers saved-ground-item durable boot handoff, not this player-projection repair.

## Initial scope: narrow offline exact-UID projection repair

Use current supported target/service-boundary and backup primitives; ship a guarded offline workflow before considering a separate live-runtime adapter. Do not require a broad new recovery platform to close this gap.

1. **Inspect:** collect current authority, owner/root/parent/revisions, physical carriers, relevant receipts, pending journals and quarantine/terminal/death conflicts in consistent snapshots. Include active and legacy carriers. Classify retained, safely evidenced missing, ambiguous and unavailable-historical-payload cases separately.
2. **Plan:** bind an exact UID set to verified historical bytes and fresh current evidence. Current authority—not the historical payload's player ID or container row IDs—determines the destination. Preserve retained roots/siblings and map restored SQL surrogate IDs to current authoritative ancestry.
3. **Approve:** produce an owner-only, tamper-evident reviewed plan with explicit target, original UID set, metadata policy and authorization. Missing historical state is a refusal, not permission to mint prototype replacements.
4. **Apply:** require verified quiescence/recipient save and login exclusion, a fresh rollback point and journal reconciliation. Revalidate all evidence and candidate absence inside a transaction; restore only approved missing physical and auxiliary rows. For this narrow mode, do not rewrite current custody/ledger, invent revisions, allocate replacement UIDs or roll back player scalars.
5. **Verify:** independently read exact target rows and topology, then exercise materialization, save, cold reconnect and restart. Emit a durable receipt and distinguish database commit from verified in-game recovery.
6. **Rollback/retry:** record exact task-created rows and prerequisites. Duplicate application must refuse or return the existing verified receipt. Never use a pre-login rollback automatically after subsequent gameplay has changed the graph.

## Metadata safety

- Preserve exact instance scalar fields, flags, materials, affects, extra descriptions and any required dependent records, not only vnum/UID/counts.
- A verified historical payload is not proof of the latest charges, condition, restrictions or lifetime. Compare newer evidence where available and require explicit handling/refusal for uncertain mutable state.
- Artifact/transient/lifetime and other restricted classes require their own verified policy; do not renew expired items by copying an older timer.
- Keep protected identities/payloads out of ordinary output and public fixtures.

## Acceptance

- [ ] Matching-engine disposable rehearsal from production-shaped synthetic or protected data; test both rollback and committed apply, then duplicate replay refusal.
- [ ] Historical owner differs from current owner; old physical row IDs are unusable; retained destination root stays untouched; multiple roots with nested contents restore correctly.
- [ ] Owner/revision change, duplicate payload elsewhere, missing ancestor, stale evidence, pending save/journal, active writer, mismatched target, tampered plan and partial auxiliary insert all refuse without partial restoration.
- [ ] Exact fields, auxiliary/dependent records and original UIDs survive first load, save, cold login and server restart; unrelated inventory/scalars/custody remain unchanged.
- [ ] Supported user-manager and system-manager boundaries both work without weakening existing checks.
- [ ] Protected receipt, truthful progress/next-action feedback, runbook and post-access rollback limitations are documented.

Historical restoration remains opt-in and separately authorized per target and recovery set. No automatic reimbursement or blanket legacy repair is requested.
````

<a id="issue-533"></a>

### #533: Do not block authenticated player login on non-core persistence failures

- Issue: https://github.com/Community-Duris/Duris/issues/533
- Opened by `xander-l` on 2026-09-20
- Labels: none
- Discussion created: #639 (Ideas)

````markdown
## Summary

Issue #513 removed persisted pet room metadata as a login admission check. The broader audit found that the player loader is still all-or-nothing across several secondary persistence, custody, gameplay, and operational dependencies.

After account authentication and intentional character-access checks pass, a player should not be held out of the game because of stale room metadata, partial item or pet corruption, restitution sidecar state, bank/history reads, transient database failures, worker availability, queue capacity, or other recoverable operational conditions.

The only player-data condition that should deny entry is complete corruption of the core playerfile such that a safe character cannot be reconstructed.

## Policy

Once the account and character are authenticated and authorized:

- Admit the player when the core player snapshot is valid.
- Treat secondary persistence failures as degraded or quarantined state.
- Treat transient database, pipeline, lock, timeout, and resource failures as retryable infrastructure conditions, not playerfile corruption.
- Preserve unresolved item, pet, restitution, and custody rows for repair; do not silently delete them.
- Permit login in a guarded recovery/read-only mode when necessary to prevent conflicting writes while persistence reconciliation is pending.
- Keep explicit authentication, account/character blocking, bans, server-capacity controls, and intentional gameplay-policy gates unless those are separately changed.

## Current blockers to address

The current code can deny entry for:

1. Death-restitution target save/login fences.
2. Load-pipeline stopped/unavailable state.
3. Duplicate requests and pending/completion queue capacity.
4. Worker timeouts, cancellation, stale results, and missing completions.
5. Database connection, transaction, query, deadline, budget, and commit failures.
6. Account projection repair or account-file reload failures.
7. Bank and gameplay-history query failures.
8. Restitution delivery/runtime sidecar inconsistencies.
9. Partial item ownership, metadata, topology, and custody inconsistencies.
10. The stale-item refusal threshold that blocks when more than 32 rows would otherwise be skipped.
11. Pet identity, pet-item, custody, prototype, and materialization failures.
12. Flat-file authority, I/O, domain, and item-repository failures.
13. Runtime pool, object, mobile, string, and revision-hydration allocation failures.
14. Legacy one-hour-rule lookup failure, multiplay policy, global locks, and capacity checks.
15. Transport inconsistencies between account/telnet and WebSocket reconnect paths.

## Proposed design

Split player loading into an admission result with explicit dispositions:

- `admitted`: complete core load.
- `admitted_degraded`: core load succeeded; one or more secondary components are quarantined, defaulted, or pending repair.
- `rejected_core_corrupt`: the core playerfile cannot be safely reconstructed.

Suggested behavior:

- Load core identity and status independently from optional domains.
- Make bank and gameplay-history reads best-effort.
- Convert item and pet row failures into lossless quarantine records with a repair reason.
- Replace the stale-item hard refusal with bounded reconciliation/quarantine that preserves authoritative custody rows and prevents normal saves from deleting unresolved data.
- Keep restitution safety by blocking conflicting operations, not login itself.
- Provide a recovery/read-only mode while a durable operation or ledger discrepancy is unresolved.
- Preserve the raw record and emit structured telemetry for every degraded component.
- Unify account, legacy nanny, reconnect, and WebSocket admission behavior.
- Distinguish playerfile corruption from infrastructure failure in player-facing messages and staff telemetry.

## Acceptance criteria

- A stale pet room value never prevents login.
- A transient database failure does not classify the playerfile as corrupt.
- A stopped or saturated load pipeline has a recovery/degraded path.
- Bank/history failures do not prevent entry.
- Partial item or pet failures preserve unresolved data and allow entry when the core playerfile is valid.
- Restitution fences do not hold login indefinitely; conflicting mutations remain protected.
- Complete core playerfile corruption is still rejected with a precise staff-visible reason.
- The same admission semantics apply to account, legacy, reconnect, and WebSocket paths.
- Tests cover every load disposition and every current rejection category.
- No repair path silently deletes authoritative item, pet, or restitution custody.
````

#### Comment 1 of 1: `xander-l`, 2026-09-20

https://github.com/Community-Duris/Duris/issues/533#issuecomment-5748488082

````markdown
Implementation status: the authorized sweep is now folded into [PR #531](https://github.com/Community-Duris/Duris/pull/531). The production login paths no longer use death-restitution/save-admission fences; core status/identity remains the only hard load stage, while component, item, pet, bank, gameplay-history, pipeline, and materialization failures enter a degraded save-quarantined mode. Copyover and synchronous fallback paths are covered as well. The room-match check in writeSavedItem remains a durable custody guard only; it is not a login gate.
````

<a id="issue-539"></a>

### #539: Improve quantity-buy syntax, shop listings, and purchase feedback

- Issue: https://github.com/Community-Duris/Duris/issues/539
- Opened by `xander-l` on 2026-09-20
- Labels: `enhancement`, `status:ready`, `priority:P2`, `area:items`
- Discussion created: #638 (Ideas)

````markdown
## Summary

After the multi-buy correctness regression is repaired in #537, improve the player-facing quantity-buy experience so the syntax is discoverable, validation is consistent, and asynchronous orders report clear aggregate results instead of misleading or repetitive messages.

This issue tracks usability and presentation. Transactional correctness, completion-driven sequencing, payment/item atomicity, cumulative capacity enforcement, and backend regression coverage remain in #537.

## Current player-experience problems

- The only documented batch form is the awkward legacy syntax `buy <item> <container> <quantity>`; a container is required even when the player wants the items in inventory.
- SQL/MariaDB-primary and flat-file-primary reject or fall back differently for missing containers and invalid quantities.
- `atoi()`-based parsing can silently interpret zero, negative, or nonnumeric quantities as a one-item purchase on the flat-file path.
- The SQL path can print `You now have ...` before asynchronous item creation has committed.
- Batch orders can print the normal shopkeeper and item-success output once per copy, producing as many as 50 repeated messages.
- `Your purchase is being processed` does not state the quantity, destination, unit price, or total.
- `Your remaining purchases could not be continued` does not state how many succeeded, how much was charged, or why the order stopped.
- Player messages expose internal phrases such as `ownership authority` instead of explaining whether the player was charged and what to do next.
- `list` does not identify stock that supports quantity purchases.
- `help buy` says the maximum quantity is 9, while the code and `docs/reference/BATCH_ITEM_COMMANDS.md` specify 50.

## Proposed command grammar

Keep the historical syntax as a compatibility alias:

```text
buy <item> <container> <quantity>
```

Add an explicit canonical form:

```text
buy <item> quantity <1-50>
buy <item> quantity <1-50> into <container>
```

Examples:

```text
buy ration quantity 10
buy #3 quantity 10 into backpack
buy arrow quantity 50 into quiver
```

Parse both forms into one typed purchase request. Quantity parsing must consume a complete decimal integer and reject zero, negative, nonnumeric, overflowed, and trailing input. Invalid input must purchase nothing.

## Player feedback

For a batch accepted for asynchronous processing, send one useful acknowledgement, for example:

```text
You order 5 iron rations at 2 gold each, for 10 gold total.
They will be placed in your leather backpack.
```

On full completion, send one aggregate result:

```text
Purchase complete: 5 iron rations were placed in your leather backpack for 10 gold.
```

On partial completion, report requested count, completed count, amount actually charged, uncharged count, and the stop reason:

```text
Purchase stopped: 3 of 5 iron rations were delivered for 6 gold.
The remaining 2 were not charged because your leather backpack is full.
```

When nothing commits:

```text
Nothing was purchased, and you were not charged.
Your leather backpack is closed.
```

When a durable purchase committed but live publication is delayed, do not advise a retry:

```text
Your purchase is safe but is still being delivered.
Please wait a moment or reconnect; do not purchase it again.
```

Keep detailed coordinator/ownership errors in structured logs rather than exposing implementation terminology to players. Quantity orders should emit one room event and one final player summary, not one message per copy.

## Shop listing and help

For produced/unlimited stock, annotate `list` with quantity support, for example:

```text
 1) An iron ration                    2 gold each  [quantity 1-50]
```

If a shop has batchable merchandise, include a short usage hint:

```text
Quantity purchase: buy <item> quantity <1-50> [into <container>]
```

Update `help buy` to document:

- The canonical and legacy forms.
- The actual 1-50 range.
- Inventory and container delivery.
- Produced-stock restriction.
- Epic-shop exclusion.
- Partial-completion and charging semantics.
- Examples using both an item name and a numbered `list` selector.

## Acceptance criteria

- The historical syntax continues to work.
- Quantity purchases can target inventory without requiring a container.
- Both persistence modes use the same parser and produce the same validation messages.
- Invalid container or quantity input purchases nothing and says so explicitly.
- A batch emits at most one acceptance message and one final summary to the player.
- Full and partial summaries include completed count and actual charge.
- Undelivered copies are explicitly reported as uncharged.
- Player-facing messages do not mention internal ownership/coordinator implementation details.
- `list` identifies quantity-capable stock.
- `help buy` and `BATCH_ITEM_COMMANDS.md` agree on the 1-50 limit and epic-shop exclusion.
- Executable tests assert parsing and exact full, partial, zero-success, busy, and committed-but-delayed messages.

## Possible later convenience

Once fixed quantities are reliable, consider `buy <item> max [into <container>]`, bounded by 50, available funds, carrying capacity, and destination capacity. This is optional and should not block the core UX improvements above.
````

#### Comment 1 of 1: `xander-l`, 2026-09-20

https://github.com/Community-Duris/Duris/issues/539#issuecomment-5749991301

````markdown
Dependency update: PR #540 has merged (resolving #537). With multi-buy transactional correctness and completion-driven sequencing in place, this player-facing usability follow-up is unblocked and marked \status:ready\.
````

<a id="issue-546"></a>

### #546: Investigate elemental aura no-op reports on Fire and Air Plane

- Issue: https://github.com/Community-Duris/Duris/issues/546
- Opened by `xander-l` on 2026-09-20
- Labels: `question`, `priority:P2`, `area:world`, `type:investigation`
- Discussion created: #637 (Q&A)

````markdown
## Player report

A player reports that casting elemental aura on both the Fire Plane and Air Plane completed with:

> Nothing seems to happen.

It is not yet known whether both casts used the same character, which rooms were used, or whether an elemental aura was already active.

## Triage status

This is an investigation, not yet a confirmed sector-handling defect.

Source reviewed at master commit 5405e6b9e3264f51d24a49de1fe5fc2603b1df17.

The spell emits the identical message from two independent branches:

1. The caster already has SPELL_ELEMENTAL_AURA or a fire, water, earth, air, or ice aura bit.
2. The current room sector is not exactly one of the four elemental-plane sector types.

A character-side aura would follow the same caster to both planes. Sources include an earlier elemental aura, other spells or abilities, equipment bitvectors, and racial/form innates. Fire elementals and efreet have innate fire aura; ice elementals have innate ice aura.

## Source-level verification

A temporary harness exercising the production spell body confirmed:

- A clean cast in SECT_FIREPLANE (11) emits the fire success message and applies four stat affects.
- A clean cast in SECT_AIR_PLANE (19) emits the air success message and applies four stat affects.
- An active elemental aura spell, any elemental/ice aura bit, or a non-plane sector emits the reported generic message.
- A second cast while the first elemental aura remains active also emits the generic message.

The no-double-aura guard dates to b3d4a9714 ("No more double auras"), so it is intentional historical behavior rather than a recent change.

## World-data audit

- plane_fire_one.wld: all 125 rooms use Fire Plane sector 11.
- plane_air_one.wld: 124 rooms use Air Plane sector 19; room 24433 uses sector 11.
- firep.wld: 142 rooms use sector 11, while nine palace/interior rooms use sector 0 and therefore take the generic no-op branch.
- airp.wld: 195 rooms use sector 19, two use sector 11, and three rare-load utility rooms use sector 0.

The help text says only "When cast on an elemental plane" and does not explain the exact room-sector requirement.

## Information needed from the reporter

- Whether both tests used the same character
- Character race, current form, class, and specialization
- Exact room vnum/title for each cast
- Staff stat-room output, including numeric sector
- Affects plus raw affected_by2/affected_by4 state immediately before each cast
- Equipped aura-granting items
- Whether an earlier elemental aura, fire aura, or full-form effect was active
- Full cast transcript and whether the prepared spell/mana was consumed
- Deployed server build/commit SHA

## Controlled reproduction

1. Use a character with no spell affects, aura bits, aura equipment, or aura-granting innate/form.
2. Enter room 25401 and confirm sector 11.
3. Cast elemental aura and capture output and character state.
4. Completely remove the resulting spell and aura, or use a second clean character.
5. Enter room 24401 and confirm sector 19.
6. Cast elemental aura and capture output and character state.

## Expected disposition

- If an aura bit was present, the mechanic is behaving as coded; improve the player-facing feedback in the linked UX issue.
- If the room belongs to a plane but has a non-plane sector, decide whether geographic plane membership or exact room sector is intended and correct the area data, implementation, or help.
- If a clean character reproduces this in sectors 11 and 19, current source and runtime disagree. Investigate the deployed binary, live world data, and unexpected/stale aura flags.



## Related issue

- #547 tracks the independently reproducible ambiguous-message/help/resource-loss problem.

````

#### Comment 1 of 1: `xander-l`, 2026-09-20

https://github.com/Community-Duris/Duris/issues/546#issuecomment-5753476311

````markdown
Live triage confirms this report is covered by the existing elemental-aura fix rather than requiring a duplicate patch.

Draft PR #553 (https://github.com/Community-Duris/Duris/pull/553) now:

- distinguishes an already-active aura from an invalid room sector;
- rejects the no-op before mana or prepared-spell consumption;
- documents the supported Fire, Water, Air, and Earth sector contract; and
- includes an ASan/UBSan runtime harness for clean casts, stale aura state, and invalid sectors.

The controlled source-level reproduction and world-data audit in this issue remain useful for confirming the deployed room/character state if a report persists after #553 is reviewed and merged. No separate #546 PR is being opened because that would duplicate the same behavior change.
````

<a id="issue-561"></a>

### #561: Telemetry: validate the live repository/schema contract before enabling the writer

- Issue: https://github.com/Community-Duris/Duris/issues/561
- Opened by `xander-l` on 2026-09-21
- Labels: `bug`, `area:telemetry`, `area:database`, `status:blocked`, `priority:P1`
- Discussion created: #636 (Ideas)

````markdown
Parent tracker: #258. Immediate mapping defect: #560.

## Problem

Telemetry repository startup currently proves only that `telemetry_interval`, `telemetry_session`, and `telemetry_config` exist by issuing `SELECT * ... LIMIT 0`. It does not prove that every column, index, type, or grant required by each enabled record serializer is compatible.

During the 2026-09-21 production incident, startup reported a usable SQL repository even though progression and combat SQL referenced columns absent from the live table. The incompatibility was discovered only when gameplay emitted the first affected record.

## Scope

- Define the complete repository/schema contract for every supported record kind.
- Validate required columns, critical types/signedness, replay identities, and required unique keys before accepting records.
- Execute validation with the telemetry service account so missing grants are detected.
- Associate validation output with the expected schema/migration version.
- If telemetry is optional, allow gameplay to start but leave telemetry explicitly disabled/degraded with a schema-incompatible reason.
- Do not admit records into a writer already known to be incompatible.

A read-only projection of every generated column set (`SELECT ... LIMIT 0`) is acceptable if it is derived from the same mappings used for writes.

## Acceptance criteria

- [ ] Removing or renaming one progression column is detected before any record is admitted.
- [ ] A missing combat column is detected without requiring combat to occur.
- [ ] Missing-table, missing-column, incompatible-type, missing-index, and permission failures are distinguishable.
- [ ] One structured, rate-limited operator message names the contract version, object, failure class, and numeric SQL error.
- [ ] Gameplay may continue only with telemetry visibly disabled/degraded; telemetry is never reported healthy.
- [ ] Successful repair/revalidation can transition the writer to ready under a documented lifecycle.
- [ ] MariaDB and MySQL integration tests cover compatible and incompatible schemas.

## Dependency

Use the corrected mappings from #560 as the expected contract.
````

<a id="issue-564"></a>

### #564: CI: run telemetry migrations and SQL repository round trips for every record kind

- Issue: https://github.com/Community-Duris/Duris/issues/564
- Opened by `xander-l` on 2026-09-21
- Labels: `bug`, `area:telemetry`, `area:database`, `status:ready`, `priority:P1`, `github_actions`
- Discussion created: #635 (Ideas)

````markdown
Parent tracker: #258. Regression to cover: #560.

## Problem

`tests/async/test_telemetry_repository.py` compiles the SQL harness by default but skips database execution unless `--sql-fixture` and a disposable-database acknowledgement are supplied. The encounter and combat-summary suites validate schema strings and in-memory producers independently, but do not round-trip those records through the SQL repository.

That split allowed the repository and migrations to be internally valid while disagreeing on column names.

## Required CI matrix

In uniquely named disposable databases:

1. Apply the complete immutable migration chain through the manifest head.
2. Initialize the repository with production-equivalent session settings.
3. Generate and apply every record kind supported by the current schema.
4. Select each row back and compare every field.
5. Replay it and require `duplicate_identical`.
6. Change one field and require `duplicate_conflict`.
7. Exercise mixed batches, rollback, transient failure, and commit ambiguity.
8. Assert typed values land in intended prefixed columns and not similarly named generic columns.
9. Run on supported MariaDB and MySQL versions.

## Acceptance criteria

- [ ] SQL execution is a required merge check and cannot silently report `SQL runtime: SKIPPED`.
- [ ] CI fails if any generated repository column is absent.
- [ ] CI fails if encounter/combat values land in generic columns.
- [ ] Record kinds 1 through 8 are round-tripped.
- [ ] Startup contract validation and permanent/transient error classification are exercised.
- [ ] Fixture resets cannot target a production or non-disposable database.
- [ ] Failure output identifies the migration, engine, record kind, and mismatched column.
- [ ] Reintroducing the current `kind` versus `progression_kind` defect fails before merge.
````

<a id="issue-565"></a>

### #565: Telemetry: define repository mappings and schema checks from one canonical column contract

- Issue: https://github.com/Community-Duris/Duris/issues/565
- Opened by `xander-l` on 2026-09-21
- Labels: `enhancement`, `area:telemetry`, `area:database`, `status:deferred`, `priority:P2`, `type:refactor`
- Discussion created: #634 (Ideas)

````markdown
Parent tracker: #258. Immediate correction: #560. Required SQL coverage: #564.

## Problem

Telemetry column names are independently repeated in immutable migrations, migration verifiers, repository string construction, report definitions, schema tests, and documentation. Manual duplication made it possible for producers, migrations, and tests to agree only with themselves.

## Scope

Introduce one canonical descriptor per record kind containing at least:

- SQL column name;
- payload member/accessor;
- SQL type and signedness;
- nullability/record-kind applicability;
- replay-identity membership;
- sensitivity/logging policy;
- report-facing semantic name where appropriate.

Repository serialization and startup schema validation must consume the same descriptor. Tests and verifier expectations should be derived from it where practical.

At minimum, replace ambiguous typed-extension mappings such as `FIELD(values, p, kind)` with explicit column names and add a linter/static test that rejects unprefixed extension fields.

Historical immutable migrations must remain immutable.

## Acceptance criteria

- [ ] Every serialized telemetry field has an explicit schema column mapping.
- [ ] Adding a payload member requires adding or explicitly acknowledging its database mapping.
- [ ] Repository writes and schema validation consume the same contract.
- [ ] Record-family prefixes cannot be silently omitted.
- [ ] Replay identities and report queries remain stable.
- [ ] All existing record-kind round-trip tests continue to pass on MariaDB and MySQL.
- [ ] The design does not generate or rewrite historical immutable migrations.
````

<a id="issue-566"></a>

### #566: Telemetry: preserve or explicitly account for queued records across restart and copyover

- Issue: https://github.com/Community-Duris/Duris/issues/566
- Opened by `xander-l` on 2026-09-21
- Labels: `enhancement`, `area:telemetry`, `area:database`, `status:deferred`, `priority:P2`
- Discussion created: #627 (Ideas)

````markdown
Parent tracker: #258. Failure handling: #562. Health reporting: #563.

## Problem

The telemetry queue and inflight batch are process memory. Restart or copyover during an SQL outage discards the backlog, and no durable coverage-gap fact necessarily reaches the database. Consumers may interpret absent telemetry as zero activity.

## Scope

Design bounded crash/copyover recovery. Preferred approach: a local spool/WAL containing producer identity, sequence, record kind, schema version, admission time, serialized payload, and checksum.

On startup/copyover, reconcile against the last committed database sequence, replay uncommitted records exactly, and discard only identical committed records.

If a full spool is intentionally rejected, persist a bounded outage ledger with first/last affected sequence and time, dropped/abandoned count, reason, and producer identity so an explicit coverage gap can be published later.

## Acceptance criteria

- [ ] Restart during a simulated SQL outage does not silently erase the backlog.
- [ ] Copyover preserves pending telemetry or produces an explicit durable gap.
- [ ] Replay is idempotent and respects producer identity.
- [ ] Storage is strictly bounded with documented disk-full behavior.
- [ ] Corruption is checksum-detected and visibly reported.
- [ ] No spool operation blocks the main game loop.
- [ ] Sensitive data does not exceed the existing telemetry contract.
- [ ] Graceful shutdown, copyover, and abrupt termination are tested.
- [ ] Operators can determine whether an incident backlog was drained, abandoned, or partially recovered.
````

<a id="issue-567"></a>

### #567: Data quality: register and reconcile the telemetry outage beginning 2026-09-21 00:49:26 UTC

- Issue: https://github.com/Community-Duris/Duris/issues/567
- Opened by `xander-l` on 2026-09-21
- Labels: `bug`, `area:telemetry`, `area:database`, `status:blocked`, `priority:P1`, `type:investigation`
- Discussion created: #633 (General)

````markdown
Parent tracker: #258. Writer fix: #560. Health reporting: #563. Durability follow-up: #566.

## Incident window

The production database contains 361 valid records for the current producer. The last successful ingest was `2026-09-21 00:49:26.2889 UTC`. Gameplay continued afterward, including at least 85 XP-log lines and 11 player-entry events observed during the initial investigation.

No progression, encounter, combat-summary, or durable coverage-gap record was committed after the stall.

## Scope

- Register the affected producer and time range in a durable data-quality ledger.
- Record the actual end time and first good post-fix sequence after deployment.
- Annotate or exclude the incomplete interval from reports and rollups.
- Reconcile sessions left with unclosed tails.
- Determine which session/login/XP facts can be reconstructed from authoritative logs.
- Do not fabricate detailed activity or combat facts that cannot be reconstructed reliably.
- Mark reconstructed facts with distinct provenance and quality flags.
- Document whether the in-memory backlog was drained, discarded, or partially recovered.

## Acceptance criteria

- [ ] Analytics cannot present the incident interval as complete coverage or valid zero activity.
- [ ] The affected producer, start/end time, and record families are queryable.
- [ ] Reconstructed facts are distinguishable from original live telemetry.
- [ ] Rollups do not treat unclosed session tails as ordinary exits.
- [ ] The incident record identifies the first trustworthy post-fix record.
- [ ] The disposition of the process-memory backlog is documented.

This is an operational/data-quality issue; it must not delay the code fix in #560.
````

<a id="issue-569"></a>

### #569: Persistence: audit, repair, and prevent player item topology rows with missing payloads

- Issue: https://github.com/Community-Duris/Duris/issues/569
- Opened by `xander-l` on 2026-09-21
- Labels: `bug`, `area:database`, `status:ready`, `priority:P1`, `area:items`, `type:investigation`
- Discussion created: #632 (General)

````markdown
## Production evidence

The current run logged 19 `player_load_materialize ... missing_payload_rows` events across eight character IDs, compared with two events across two character IDs in the immediately preceding run. The runtime explicitly marks these cases `recovery=operator_repair`.

The condition is not new, but the current incidence is elevated and player-load behavior may hide or discard inaccessible item references.

## Scope

- Build a read-only inventory of every topology reference whose required payload row is missing.
- Classify orphaned topology, missing item payload, deliberately retired content, duplicate UID, and partial migration cases.
- Provide an idempotent, dry-run-first repair workflow with operator review.
- Preserve legitimate equipment/container ownership and nested topology.
- Add write-time/database guards preventing topology from committing without required payload state.
- Measure new occurrences separately from historical rows being repaired.

## Acceptance criteria

- [ ] A dry run identifies all affected characters, references, and classifications without exposing private data in logs.
- [ ] Repair is idempotent and restart-safe.
- [ ] The loader does not silently discard unresolved references.
- [ ] Legitimate nested containers, equipped items, and custody relationships are preserved.
- [ ] New writes cannot introduce the same missing-payload state.
- [ ] Metrics distinguish new violations from known historical repair work.
- [ ] The eight currently observed character IDs receive documented operator-reviewed dispositions.
- [ ] Tests cover partial save, interrupted migration, nested containers, duplicates, and retired definitions.
````

#### Comment 1 of 4: `xander-l`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/569#issuecomment-5754798585

````markdown
## Relationship to existing work

- #533 owns degraded player admission when secondary item data is incomplete; this issue owns the production inventory, repair workflow, and prevention of new missing-payload topology.
- Closed #125 contains earlier topology-mismatch context. Reuse its classifications where they remain valid, but re-audit against current master and current production evidence.
````

#### Comment 2 of 4: `xander-l`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/569#issuecomment-5755489460

````markdown
The prevention slice is merged in #574 (`8e2d627495ce6028a37f0bcbcb2428808a5f5195`).

Any durable ownership row with a missing item payload now degrades the item load and fences ordinary saves/checkpoints, so a partial runtime inventory cannot rewrite durable mappings. When that payload gap is the only degraded component, a non-arena death is allowed only through the immutable disputed-custody disposition and selects that path before attempting the count-sensitive transfer.

Local validation covered the focused load/save/custody contracts, clean flat-file and MariaDB builds, and both cold-load/death/restart journeys. The MariaDB regression verified custody was durable before release and remained stable after restart.

This prevents recurrence; it does not restore inventory from incidents that already occurred. Existing recovery work remains tracked separately in #526 and the incident record in #570.
````

#### Comment 3 of 4: `xander-l`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/569#issuecomment-5756258192

````markdown
Root-cause correction to the earlier “prevents recurrence” note:

Read-only production comparison around the 2026-09-21 incident shows that #574 fences a character only after a later load has already detected missing payload. It does not prevent the initial write that creates the gap.

The fresh-write path is:

1. Account-bound reward materialization marks the reward container `ITEM_NORENT`, then admits the complete object tree into authoritative player custody.
2. Ordinary snapshot capture filters `ITEM_NORENT` before recording the object and returns before traversing that container’s children.
3. The player snapshot repository deletes/replaces `player_items` without proving that the replacement graph exactly matches active non-inline `item_current_owner` custody.
4. One valid-looking save can therefore retain custody rows while deleting the only payload for the omitted root and every child under it.

The affected production save omitted one reward-container tree (the wrapper plus its ordinary non-coin contents); the remaining inline coin payload was independently recoverable. Earlier smaller gaps show this is a general invariant failure, not a one-off crash artifact.

A related death-path defect amplified the incident: `make_corpse()` calls the account-reward dissolve hook while a PC corpse is still empty; PC inventory is transferred asynchronously afterward, so the hook cannot see the reward container at that point.

The prevention slice being prepared will:

- stop classifying account rewards as generic `NORENT` objects, because they already have explicit summon/dismiss/death lifecycle policy;
- serialize any `NORENT` object that nevertheless has active durable custody (authority wins over a lossy filter);
- lock and compare the complete replacement item graph against active custody, including root/parent/vnum topology, before deleting any payload rows; inline coin custody remains valid without a `player_items` row;
- co-mark equipment and inventory so the comparison and replacement are one complete graph;
- emit a distinct redacted metric/alert for rejected custody/payload mismatches.

The existing historical repair and operator-disposition scope in this issue remains open.
````

#### Comment 4 of 4: `xander-l`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/569#issuecomment-5756548399

````markdown
Preventive fix merged in #585 (`4a4dd5a60489b9c872245410d15882a5675fd828`).

The confirmed unsafe path was:

1. account reward containers were marked `NORENT`;
2. snapshot capture skipped the `NORENT` root and returned before traversing its children;
3. the repository deleted/replaced `player_items` without checking the new graph against active `item_current_owner` custody;
4. custody rows therefore survived while the corresponding payload rows disappeared.

#585 prevents fresh normal saves from creating that condition in three layers: reward containers no longer acquire `NORENT`; active durable custody overrides `NORENT` during capture; and complete player-item saves now lock and compare the exact UID/root/parent/vnum custody graph before any destructive payload replacement. A mismatch is rejected and rolled back, preserving the prior revision and payload, and gets its own health counter/status signal. Inline coins remain an explicit valid exception because their authoritative payload lives in `coin_payload`.

This does **not** reconstruct payload that was already lost, so historical repair remains open. Also still open here: the account-reward death hook can observe an empty PC corpse before asynchronous inventory transfers populate it. That lifecycle/order issue needs an explicit custody-aware move/retirement design and is not claimed as fixed by #585.

Local validation included strict MariaDB and flat-file builds after rebasing onto current `master`, focused capture/pipeline/worker/ownership/reward/lifecycle tests, and a disposable MariaDB nested-tree regression proving that an omitted child is rejected while the previous revision and payload rows remain intact.
````

<a id="issue-570"></a>

### #570: Persistence: correlate corpse rejection and critical-command integrity recovery to a terminal custody outcome

- Issue: https://github.com/Community-Duris/Duris/issues/570
- Opened by `xander-l` on 2026-09-21
- Labels: `bug`, `area:database`, `status:ready`, `priority:P2`, `area:items`, `type:investigation`
- Discussion created: #631 (General)

````markdown
## Production evidence

A player death in the current run produced this sequence:

- corpse items in flight and recovery scheduled;
- `corpse action=rejected_preserved` with `item_uid=0`, error 90, disputed 1;
- a critical-command integrity failure;
- successful death-disposition completion one second later.

This alert class is recurring, but current logs do not prove whether `preserved` means safely recoverable, quarantined, restored, or merely not deleted.

## Scope

- Assign one non-sensitive correlation ID across death save, corpse transfer, critical-command journal, dispute, retry, and terminal disposition.
- Give numeric errors named/documented operator meanings.
- Publish an explicit terminal custody state: durable, restored, quarantined, unresolved, or safely retired.
- Rate-limit repeated identical alerts while retaining a summary count and elapsed time.
- Provide an operator query for unresolved preserved items and their recovery owner.

## Acceptance criteria

- [ ] Every event in one recovery chain carries the same correlation ID.
- [ ] Error 90 and other expected codes have stable named meanings.
- [ ] `item_uid=0` is handled explicitly and cannot conceal a lost item identity.
- [ ] A completed death disposition cannot coexist silently with unresolved item custody.
- [ ] Operators can enumerate unresolved cases without reading raw log files.
- [ ] Repeated retries produce bounded logs plus a terminal summary.
- [ ] Tests cover `item_uid=0`, disputed transfer, retry exhaustion, restart during recovery, and successful reconciliation.
````

#### Comment 1 of 3: `xander-l`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/570#issuecomment-5754798604

````markdown
## Relationship to existing work

- #486 owns balanced death/world/recovery accounting.
- #331 owns audited restitution for quarantined disputed-death items.
- This issue owns causal correlation, explicit terminal custody state, operator visibility, and bounded alerting. It should consume—not duplicate—the authoritative custody/restitution operations from those issues.
````

#### Comment 2 of 3: `xander-l`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/570#issuecomment-5754959076

````markdown
## Confirmed root cause from the current production run (sanitized)

Read-only correlation of the active DMS run at commit `5405e6b9e3264f51d24a49de1fe5fc2603b1df17` narrows the reported sequence to a durable/live topology mismatch, not an oversized ordinary death payload.

- Six player deaths occurred after this process started. Five completed the ordinary corpse-custody path. One entered disputed-death handling.
- Twenty-three seconds before that death, the affected character's load reported `missing_payload_rows=15` plus one in-memory topology repair. The same missing-payload condition had appeared on earlier loads in this run, so the initiating data problem predates the death.
- The death submitted a multi-root corpse transfer containing 15 live items, all top-level roots. The repository returned `EMSGSIZE` because the authoritative selected subtree contained 16 rows across those same 15 roots. This is the `selected.size() != payload.item_count` refusal in `src/item/item_transfer_repository.c`, not the 384 KiB command-payload ceiling.
- The unmatched sixteenth row is a durable child whose parent/root is one of the captured live roots. It has legitimate prior custody-ledger history, but no loadable physical payload and was therefore absent from both the live object graph and the death-custody capture.
- The fail-closed disposition then quarantined 16 authority rows: the 15 captured live items plus that unmatched child. The durable death record contains a 9,746-byte snapshot and 15 custody rows/15 roots. None of those rows currently materializes in `player_items` or `corpse_items`, and no restitution receipt/delivery exists for this death.

This explains the player-visible loss: the visible equipment was moved out of normal player/corpse projections into disputed-death quarantine after the batch mismatch. The evidence does **not** show those 15 captured items being silently deleted, but they remain inaccessible until the existing reviewed restitution path is used.

### Issue ownership / fix boundary

- #569 owns the upstream inventory, repair, and prevention of active ownership rows whose required payload is missing.
- This issue owns making the death-chain consequence explicit and operator-actionable instead of ending at `rejected_preserved error=90` plus `death_disposition_completed`.

A regression should seed an active durable-only descendant under a carried live root, admit the degraded player load, then exercise death. It should assert a named topology-cardinality refusal, exact terminal custody accounting (captured versus unmatched rows), a queryable unresolved state, and a deterministic recovery action. Raw character, item, room, operation, and database identifiers are intentionally omitted here.
````

#### Comment 3 of 3: `xander-l`, 2026-09-21

https://github.com/Community-Duris/Duris/issues/570#issuecomment-5755489491

````markdown
The recurrence-prevention fix is merged in #574 (`8e2d627495ce6028a37f0bcbcb2428808a5f5195`).

The loader now treats any missing item payload as a degraded item graph, blocks ordinary persistence from that partial snapshot, and routes an otherwise-clean non-arena death directly into durable disputed custody. This removes the 15-materialized-versus-16-owned size-mismatch path observed in this incident.

The exact flat-file and MariaDB cold-load/death/restart journeys passed locally. This merge does not automatically restore the already-quarantined incident inventory; that recovery remains within #526/#570. No production deploy, restart, or database mutation was performed as part of this PR.
````

<a id="issue-598"></a>

### #598: Add player-facing feedback for bartender kill-quest XP

- Issue: https://github.com/Community-Duris/Duris/issues/598
- Opened by `xander-l` on 2026-09-21
- Labels: `bug`, `area:output`, `priority:P2`, `area:world`
- Discussion created: #630 (Ideas)

````markdown
## Summary

Bartender kill quests appear to award their quest experience, but players do not receive feedback when that experience is granted. This makes the quest bonus look as though it is missing.

## Investigation

- `src/world/world_quest.c:309-343` (`quest_kill`) computes the per-kill reward and calls `gain_exp(..., EXP_WORLD_QUEST)`.
- `src/world/limits.c:896-919` (`display_gain`) only emits live XP feedback when `type == EXP_KILL`; `EXP_WORLD_QUEST` is excluded.
- `src/combat/fight.c:3215-3231` invokes `quest_kill` from the central death path, so the award path is present for qualifying kills.
- The result is that the character XP total can increase without a visible quest-specific XP message.

## Requested behavior

When a qualifying bartender kill quest awards experience, show a clear player-facing message with the amount and identify it as quest XP. Completion/turn-in feedback should remain distinct from per-kill quest XP. The message should respect the existing experience-display preference if that is the intended convention.

## Acceptance criteria

- Each qualifying kill produces one clear `EXP_WORLD_QUEST` feedback line showing the awarded amount.
- Normal kill XP and bartender quest XP remain separate and are not double-counted.
- No quest-XP feedback is emitted for non-qualifying kills, capped/no-reward cases, or targets that are not actually credited.
- Add or update a regression test covering the `EXP_WORLD_QUEST` award and feedback path.

## Reproduction

1. Accept a bartender `FIND_AND_KILL` quest.
2. Kill the matching target.
3. Observe that the kill-quest count advances and the character may gain XP, but no quest-specific XP gain is displayed.
````

<a id="issue-616"></a>

### #616: Flight Dragon network: learnable destinations, distance-priced tickets and discovery EXP (mobs 47015–47041)

- Issue: https://github.com/Community-Duris/Duris/issues/616
- Opened by `moshehbenavraham` on 2026-09-22
- Labels: `enhancement`, `area:database`, `status:deferred`, `priority:P2`, `area:world`, `area:economy`
- Discussion created: #629 (Ideas)

````markdown
> **Priority:** Fotenak (builder) described this as a new feature that is **not critical**. This issue records the design and the investigation so the work can be picked up later; it can be deferred.

## Summary

Fotenak redesigned the flight-dragon travel system and already landed the world-file side in the vehicles area (`areas/*/vehicles.*`). The code side was never written. [`src/world/transport.c`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c) still runs the old fixed-route system from a hard-coded table, so:

- The **11 new flight mobs 47031–47041** exist in `vehicles.mob` but **never load**: nothing spawns them.
- **12 of the 16 existing flight mobs** now belong at different pads, and the builder renamed and redescribed them for their new homes. The code still spawns them at their old pads. For example, the wyvern wearing Storm Port's crest sits at Quietus Quay.

In the new design every flight mob is a named **Flight Destination**:

- A character **learns** a destination by typing `list` at that destination's flight mob.
- From any flight mob, the character can fly to **any destination they know**.
- The **ticket price depends on the distance** between the two stops.
- A few **Extra Destinations** keep working the way the current system does: one-way trips at a fixed price, from one specific mob.
- Each newly learned destination gives an **EXP reward that grows with the number of destinations found**.

## Builder report (Fotenak, Discord)

> there's a whole project in the vehicles world file that is still pending coding
> (you might notice that like 50% of the mobs don't load)
> mobs 47031-47041 (okay not 50%) i added for new destinations
>
> well its a new feature thing so its not that critical
>
> so the idea is that there are flight destinations that players can learn, and their cost is dynamic based on how far each one is to each other
>
> **Updated Flight Dragon system:**
>
> List of Destinations, with corresponding Destination Name, room #, corresponding mob.
>
> Each player has a built-in list of Flight Destinations that they can travel between. New characters start with no Destinations on their list, but when they type "list" at a new flight vehicle mob, it adds that Destination to their Destination list. Ticket price based on distance between destinations.
>
> "Extra Destinations" are 1-way trips that are hard-set price, and work like the original flight path system.
>
> so basically when someone discovers a new flight dragon and types "list" at it for the first time, it adds that flight dragon's "destination name" to their flight list, and now they can fly there from any other flight dragon
>
> oh and we wanted to make it so every time you add a destination to your destinations list, it gives you an exp reward, and it goes up with the more you find
> (not sure how much exp, but maybe like +10k for each)

When asked, Fotenak confirmed that the original flight path system is still in the game. It is the current `transport.c` system, which dates back to at least 2009.

<details>
<summary>Full Discord conversation, verbatim</summary>

```text
PM]Fotenak: there's a whole project in the vehicles world file that is still pending coding
[11:54 PM]Fotenak: (you might notice that like 50% of the mobs don't load)
[11:55 PM]Fotenak: mobs 47031-47041 (okay not 50%) i added for new destinations
[11:56 PM]Max aka Mosheh: ok want me to look into that too?
[11:56 PM]Fotenak: well its a new feature thing so its not that critical
[11:56 PM]Max aka Mosheh: whatever you need, i could create the issue now and put a note its not critical and can be put off for now too
[11:56 PM]Max aka Mosheh: that way there is a record of it
[11:58 PM]Fotenak: so the idea is that there are flight destinations that players can learn, and their cost is dynamic based on how far each one is to each other
[11:58 PM]Fotenak: i wrote a good couple paragraphs about it to someone let me see if i can find it
[11:59 PM]Max aka Mosheh: great, the more details you give, the better chance it will turn out the way you want ;p
[11:59 PM]Fotenak: Updated Flight Dragon system:

List of Destinations, with corresponding Destination Name, room #, corresponding mob.

Each player has a built-in list of Flight Destinations that they can travel between. New characters start with no Destinations on their list, but when they type "list" at a new flight vehicle mob, it adds that Destination to their Destination list.  Ticket price based on distance between destinations.

"Extra Destinations" are 1-way trips that are hard-set price, and work like the original flight path system.
[12:00 AM]Max aka Mosheh: there is a flight path system?  it was taken out?  you happen to remember how long ago it existed?
[12:00 AM]Fotenak: there is a spreadsheet that accompanies this:
https://docs.google.com/spreadsheets/d/19gZNDKk_n4MWB1tkpmNHXTmnLNErQhoSaAFEap2dbsA/edit?usp=drive_link
Google Docs
new flight paths
Image
[12:01 AM]Fotenak: its still in
[12:02 AM]Max aka Mosheh: ok
[12:03 AM]Fotenak: so basically when someone discovers a new flight dragon and types "list" at it for the first time, it adds that flight dragon's "destination name" to their flight list, and now they can fly there from any other flight dragon
[12:13 AM]Fotenak: oh and we wanted to make it so every time you add a destination to your destinations list, it gives you an exp reward, and it goes up with the more you find
[12:13 AM]Fotenak: (not sure how much exp, but maybe like +10k for each)
```

</details>

## The spreadsheet

The data comes from the spreadsheet [**new flight paths**](https://docs.google.com/spreadsheets/d/19gZNDKk_n4MWB1tkpmNHXTmnLNErQhoSaAFEap2dbsA/edit?usp=drive_link). The "Image" in the Discord post appears to be the link's preview image. The sheet has **two tabs**:

- **NEW FLIGHT VEHICLES** (gid 1897554044) is the new design. Its CSV export is identical, apart from line endings, to the CSV we were given (`tmp/new-flight-paths.csv`). Every value is reproduced below.
- **old routes** (gid 0) documents the current system. Its 20 rows match today's `transport_routes[]` row for row: the same pads, destinations, prices and level gates. It ends with one extra row that has only a destination name, **"Behemoth Herders"** (see the open questions). Reproduced verbatim at the end of this section.

### Destinations (27)

| Mob | Old mob name | New mob name | Quest? | Load room | Destination name | Destination name (ANSI) |
| --- | --- | --- | --- | --- | --- | --- |
| 47027 | Krrlytstalarryn, the ancient red dragon | Krrlytstalarryn, the ancient red dragon | Y | 619771 | Swamp of Chief Blood-Eye | `&+GS&+gw&+Ga&+gm&+Gp &+gof &+GChief &+rBlood-&+RE&+ry&+Re&N` |
| 47015 | huge skeletal dragon | Corrosyvile, the ancient black dragon | Y | 576577 | The Isle of Undeath | `&+LThe Isle of &NUndeath` |
| 47016 | mighty gryphon | a huge wyvern |  | 635756 | Quietus Quay | `&+mQuietus Quay&N` |
| 47017 | a giant green dragon | a mailed wyvern |  | 588326 | Storm Port | `&+WSto&+Lrm Port&N` |
| 47018 | huge hippogryph | an armored wyvern |  | 606262 | Bloodstone Keep | `&+RBloodstone Keep&N` |
| 47019 | flying carpet | a great white hippogriff |  | 514072 | Myrabolus | `&+MMyrabolus&N` |
| 47020 | emerald dragon | a great white griffin |  | 582084 | The City of Torrhan | `&+WThe City of &+YTorrhan&N` |
| 47021 | powerful gryphon | a huge griffin |  | 543701 | Ugta | `&+yUgta&N` |
| 47022 | hippogryph | a flying carpet |  | 545407 | Venan'Trut | `&+YVenan'Trut&N` |
| 47023 | onyx dragon | Azerathrax, the ancient blue dragon | Y | 564319 | Fort Boyard | `&+rFort &+RBoyard&N` |
| 47024 | a great blue drake | a large wyvern |  | 622276 | Sarmiz'Duul | `&+ySarmiz'Duul&N` |
| 47025 | a saddled fire drake | a harnessed roc |  | 519043 | Fort Khoralator | `&+WFort &+CKhoralator&N` |
| 47026 | a GREAT wyvern | a harnessed griffin |  | 543662 | Kimordril | `&+YKimordril&N` |
| 47028 | a mighty griffon | a harnessed frost drake |  | 522247 | Helgor Outpost | `&+RHel&+rgor &+WOutpost&N` |
| 47029 | a lithe black drake | a harnessed wyvern |  | 631413 | Clan Shatter Stone | `&+WClan Shatter Stone&N` |
| 47030 | a saddled white drake | Cryoss, the ancient white dragon | Y | 514279 | Bone Fort Inn | `&+WBone Fort Inn&N` |
| 47031 | — (new mob) | a mighty roc |  | 533479 | Winterhaven | `&+WWinterhaven&N` |
| 47032 | — (new mob) | a mighty wyvern |  | 584293 | Shady Grove | `&+GShady Grove&N` |
| 47033 | — (new mob) | a mighty griffin |  | 570024 | Tharnadia | `&+WTharnadia&N` |
| 47034 | — (new mob) | a large hippogriff |  | 529229 | Fenaline | `&+cFenaline` |
| 47035 | — (new mob) | a large griffin |  | 546144 | Canderthal Harbor | `&+WCanderthal Harbor&N` |
| 47036 | — (new mob) | Aurumax, the ancient copper dragon | Y | 575328 | Nizari | `&+yNizari&N` |
| 47037 | — (new mob) | Verdax, the ancient jade dragon | Y | 641295 | The Jade Empire | `&+gThe &+GJade &+gEmpire&N` |
| 47038 | — (new mob) | a great white giant eagle |  | 634060 | Manshaka | `&+LM&+ra&+Ln&+rs&+Lh&+ra&+Lk&+ra&N` |
| 47039 | — (new mob) | a huge skeletal dragon |  | 577835 | Varathorn Keep | `&+WV&Na&+Wr&Na&+Wt&Nh&+Wo&Nr&+Wn &+LKeep&N` |
| 47040 | — (new mob) | a large wyvern |  | 616547 | Thur'Gurax | `&+rThur'Gurax&N` |
| 47041 | — (new mob) | Glimmyris, the great faerie dragon | Y | 557220 | Moonshae Island | `&+GMoonshae &+YIsland&N` |

The sheet ends with an empty placeholder row for **47042**.

### Extra Destinations (one-way, fixed price)

| From | To room | Name | ANSI name | Min level | Cost | Rooms flown | Room title | Today |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 47027 Swamp of Chief Blood-Eye (619771) | 620606 | A Huge Cavern on the Bloodyfist Mountains | `&+yA Huge Cavern &+Lon the &+rBloodyfist &+yMountains&N` | 51 | 100 | 37 | An Entrance to a Huge Cavern | 50p, level 51+ |
| 47015 The Isle of Undeath (576577) | 579365 | A Desolate Island | `&+LA Desolate &+yIsland&N` | 51 | 100 | 19 | The Lifeless Plains of a Desolate Island | 200p, level 51+ |
| 47017 Storm Port (588326) | 637082 | Storm Port Stronghold | `&+WSto&+Lrm Port Stronghold&N` | 1 | 10 | 166 | A Patch of Grass | none (new route) |

The sheet gives no currency for "Extra Destination Cost". The current code prices every route in platinum, so these are assumed to be platinum.

<details>
<summary>"NEW FLIGHT VEHICLES" tab, verbatim CSV (same as <code>tmp/new-flight-paths.csv</code>)</summary>

```csv
Mob Vnum,Old Mob Name,New Mob Name,Quest?,Load Room Vnum,Destination Name,Destination Name (ANSI),Extra Destination Min Level,Extra Destination Cost,Extra Destination #,Extra Destination Name,Extra Destination Name (ANSI)
47027,"Krrlytstalarryn, the ancient red dragon","Krrlytstalarryn, the ancient red dragon",Y,619771,Swamp of Chief Blood-Eye,&+GS&+gw&+Ga&+gm&+Gp &+gof &+GChief &+rBlood-&+RE&+ry&+Re&N,51,100,620606,A Huge Cavern on the Bloodyfist Mountains,&+yA Huge Cavern &+Lon the &+rBloodyfist &+yMountains&N
47015,huge skeletal dragon,"Corrosyvile, the ancient black dragon",Y,576577,The Isle of Undeath,&+LThe Isle of &NUndeath,51,100,579365,A Desolate Island,&+LA Desolate &+yIsland&N
47016,mighty gryphon,a huge wyvern,,635756,Quietus Quay,&+mQuietus Quay&N,,,,,
47017,a giant green dragon,a mailed wyvern,,588326,Storm Port,&+WSto&+Lrm Port&N,1,10,637082,Storm Port Stronghold,&+WSto&+Lrm Port Stronghold&N
47018,huge hippogryph,an armored wyvern,,606262,Bloodstone Keep,&+RBloodstone Keep&N,,,,,
47019,flying carpet,a great white hippogriff,,514072,Myrabolus,&+MMyrabolus&N,,,,,
47020,emerald dragon,a great white griffin,,582084,The City of Torrhan,&+WThe City of &+YTorrhan&N,,,,,
47021,powerful gryphon,a huge griffin,,543701,Ugta,&+yUgta&N,,,,,
47022,hippogryph,a flying carpet,,545407,Venan'Trut,&+YVenan'Trut&N,,,,,
47023,onyx dragon,"Azerathrax, the ancient blue dragon",Y,564319,Fort Boyard,&+rFort &+RBoyard&N,,,,,
47024,a great blue drake,a large wyvern,,622276,Sarmiz'Duul,&+ySarmiz'Duul&N,,,,,
47025,a saddled fire drake,a harnessed roc,,519043,Fort Khoralator,&+WFort &+CKhoralator&N,,,,,
47026,a GREAT wyvern,a harnessed griffin,,543662,Kimordril,&+YKimordril&N,,,,,
47028,a mighty griffon,a harnessed frost drake,,522247,Helgor Outpost,&+RHel&+rgor &+WOutpost&N,,,,,
47029,a lithe black drake,a harnessed wyvern,,631413,Clan Shatter Stone,&+WClan Shatter Stone&N,,,,,
47030,a saddled white drake,"Cryoss, the ancient white dragon",Y,514279,Bone Fort Inn,&+WBone Fort Inn&N,,,,,
47031,,a mighty roc,,533479,Winterhaven,&+WWinterhaven&N,,,,,
47032,,a mighty wyvern,,584293,Shady Grove,&+GShady Grove&N,,,,,
47033,,a mighty griffin,,570024,Tharnadia,&+WTharnadia&N,,,,,
47034,,a large hippogriff,,529229,Fenaline,&+cFenaline,,,,,
47035,,a large griffin,,546144,Canderthal Harbor,&+WCanderthal Harbor&N,,,,,
47036,,"Aurumax, the ancient copper dragon",Y,575328,Nizari,&+yNizari&N,,,,,
47037,,"Verdax, the ancient jade dragon",Y,641295,The Jade Empire,&+gThe &+GJade &+gEmpire&N,,,,,
47038,,a great white giant eagle,,634060,Manshaka,&+LM&+ra&+Ln&+rs&+Lh&+ra&+Lk&+ra&N,,,,,
47039,,a huge skeletal dragon,,577835,Varathorn Keep,&+WV&Na&+Wr&Na&+Wt&Nh&+Wo&Nr&+Wn &+LKeep&N,,,,,
47040,,a large wyvern,,616547,Thur'Gurax,&+rThur'Gurax&N,,,,,
47041,,"Glimmyris, the great faerie dragon",Y,557220,Moonshae Island,&+GMoonshae &+YIsland&N,,,,,
47042,,,,,,,,,,,
```

</details>

<details>
<summary>"old routes" tab, verbatim CSV</summary>

```csv
Mob Vnum,Old Mob Name,Mob Load Room,Start Room,Destination Room,Old Destination Name,Cost,Min Level,Max Level,Extra Destination?
47027,ancient red dragon,619771,619771,620606,A Huge Cavern on the Bloodfist Mountains,50,51,0,620606
47015,huge skeletal dragon,576577,576577,579365,A Desolate Island,200,51,0,579365
47016,mighty gryphon,606262,606262,635756,Quietus Quay,20,0,0,No
47016,mighty gryphon,606262,606262,588326,Storm Port,20,0,0,No
47017,giant green dragon,635756,635756,606262,Bloodstone Keep,20,0,0,No
47018,huge hippogryph,588326,588326,606262,Bloodstone Keep,20,0,0,No
47021,powerful gryphon,543701,543701,514072,Myrabolus,10,0,0,No
47021,powerful gryphon,543701,543701,582084,The City of Torrhan,10,0,0,No
47025,saddled fire drake,582084,582084,543701,Ugta,10,0,0,No
47022,hippogryph,514072,514072,543701,Ugta,10,0,0,No
47020,emerald dragon,580080,580080,545407,Venan'Trut,50,47,0,No
47019,flying carpet,545407,545407,564319,Fort Boyard,50,46,0,No
47019,flying carpet,545407,545407,622276,Sarmiz'Duul,50,46,0,No
47019,flying carpet,545407,545407,580080,The City of Torrhan,50,46,0,No
47023,onyx dragon,622276,622276,545407,Venan'Trut,50,47,0,No
47024,great blue drake,563522,563522,545407,Venan'Trut,50,47,0,No
47030,saddled white drake,543662,543662,519043,Fort Khorcalator,100,0,0,No
47028,mighty griffon,519043,519043,543662,Kimordril,100,0,0,No
47029,lithe black drake,631413,631413,522247,Helgor Outpost,100,0,0,No
47026,GIANT wyvern,522247,522247,631413,Clan Shatter Stone,100,0,0,No
,,,,,Behemoth Herders,,,,No
```

</details>

## How the flight service works today

All links point at master [`a71fdfee7`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8).

- **Two hard-coded tables drive the service.** [`transport_routes[]`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L49-L116) holds 20 one-way routes. Each has an origin room, a destination room, a display name, a price in platinum, and a min/max level. [`transports[]`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L118-L143) maps 16 mob vnums to their origin rooms.
- **Boot.** [`initialize_transport()`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L232-L373) runs once during startup, after file copyover or Redis recovery (or the Redis fallback) has restored the world. It:
  - [precomputes each route's path](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L234-L251) with `dijkstra(..., valid_flying_edge, ...)`, printing `no route found` to stderr when that fails;
  - [attaches the `flying_transport` proc](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L259) to each listed mob;
  - keeps exactly one dragon per listed mob, spawning a missing one at its origin and retiring duplicates;
  - makes sure each origin has one [sign, obj 420](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L260-L283).
- **`list`.** [`flying_transport_cmd_list`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L375-L423) shows the routes whose origin is the mob's current room and whose level gates the player passes. `IS_TRUSTED` bypasses the gates.
- **`buy <n>`.** [`flying_transport_cmd_buy`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L425-L497) charges `cost_in_plat * 1000` coins. It hands over [ticket obj 47008](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/areas/obj/vehicles.obj#L82-L89) with [`value[6]` = mob vnum and `value[7]` = **index into `transport_routes[]`**](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L481-L489).
- **`give ticket <mob>`.** [`flying_transport_cmd_give`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L499-L564) consumes the ticket, mounts the player (`LNK_RIDING`) and starts `event_flying_transport_move`. The dragon flies the precomputed path one room per event. At the destination the rider dismounts, and the dragon [flies home along the reversed path](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L735-L801).
- **While flying**, the rider can only use `look`, `score`, `inventory`, `attributes`, `news`, `petition` and `toggle` ([L609–L618](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L609-L618)). Everything else gets "you're holding on for dear life!".
- **Flight edges.** [`VALID_FLYING_EDGE`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/graph.h#L108-L113) needs a two-way exit inside the **same zone** that is not `EX_BLOCKED`. Every stop in this project is on the surface map: zone #5000, rooms 500000–659999, a 400×400 grid where `vnum = 500000 + 400·y + x`. The grid **wraps on both axes**: room 500000's north exit leads to 659600 and its west exit to 500399.
- **Recovery.** [`transport_snapshot`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.h#L4-L11) stores the origin and destination **room vnums**, the state, the step and the rider's name. It is used for copyover v13 and Redis schema 12 (`TRN1` tail). [`transport_restore()`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L177-L201) finds the route again from (origin, destination). If a snapshot's origin no longer matches the configured origin, [`transport_land_at_home()`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L203-L230) brings the dragon home. See [`docs/operations/WORLD_SINGLETON_RECOVERY.md`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/docs/operations/WORLD_SINGLETON_RECOVERY.md) (#235, #315).

### Current routes, for reference

| # | Mob serving the origin today | From | To | Price | Levels | Rooms flown | Platinum per room |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 47027 | 619771 (Krrlytstalarryn pad) | 620606 A Huge Cavern on the Bloodfist Mountains | 50p | 51+ | 37 | 1.35 |
| 1 | 47015 | 576577 (skeletal dragon pad) | 579365 A Desolate Island | 200p | 51+ | 19 | 10.53 |
| 2 | 47016 | 606262 Bloodstone Keep | 635756 Quietus Quay | 20p | — | 180 | 0.11 |
| 3 | 47016 | 606262 Bloodstone Keep | 588326 Storm Port | 20p | — | 109 | 0.18 |
| 4 | 47017 | 635756 Quietus Quay | 606262 Bloodstone Keep | 20p | — | 180 | 0.11 |
| 5 | 47018 | 588326 Storm Port | 606262 Bloodstone Keep | 20p | — | 109 | 0.18 |
| 6 | 47021 | 543701 Ugta | 514072 Myrabolus | 10p | — | 103 | 0.10 |
| 7 | 47021 | 543701 Ugta | 582084 The City of Torrhan | 10p | — | 113 | 0.09 |
| 8 | 47025 | 582084 Torrhan | 543701 Ugta | 10p | — | 113 | 0.09 |
| 9 | 47022 | 514072 Myrabolus | 543701 Ugta | 10p | — | 103 | 0.10 |
| 10 | 47020 | 580080 Torrhan (2nd pad) | 545407 Venan'Trut | 50p | 47+ | 214 | 0.23 |
| 11 | 47019 | 545407 Venan'Trut | 564319 Fort Boyard | 50p | 46+ | 159 | 0.31 |
| 12 | 47019 | 545407 Venan'Trut | 622276 Sarmiz'Duul | 50p | 46+ | 261 | 0.19 |
| 13 | 47019 | 545407 Venan'Trut | 580080 The City of Torrhan (2nd pad) | 50p | 46+ | 214 | 0.23 |
| 14 | 47023 | 622276 Sarmiz'Duul | 545407 Venan'Trut | 50p | 47+ | 261 | 0.19 |
| 15 | 47024 | 563522 Fort Boyard (old pad) | 545407 Venan'Trut | 50p | 47+ | 160 | 0.31 |
| 16 | 47030 | 543662 Kimordril | 519043 Fort Khoralator | 100p | — | 243 | 0.41 |
| 17 | 47028 | 519043 Fort Khoralator | 543662 Kimordril | 100p | — | 243 | 0.41 |
| 18 | 47029 | 631413 Clan Shatter Stone | 522247 Helgor Outpost | 100p | — | 161 | 0.62 |
| 19 | 47026 | 522247 Helgor Outpost | 631413 Clan Shatter Stone | 100p | — | 161 | 0.62 |

Today's prices have no relation to distance. They range from 0.09 to 10.5 platinum per room flown.

### Why 47031–47041 don't load

- `transports[]` has no entries for them, so `initialize_transport()` never spawns them and never attaches the proc.
- No zone file has an `M` reset for any vnum from 47015 to 47042. That part is expected: code spawns flight mobs, not zone resets.

### World data vs. code: the placements have drifted

`4ee13487a` (2026-06-11) renamed and redescribed 15 of the 16 mobs from 47015 to 47030 (all except 47027) and added 47031–47041. It re-landed "zone updates from fotenak", which first went in as `0fa96b480` and was reverted in `1538cfcc4`. `transports[]` was never updated:

| Mob | Name in the mob file now | Spawned today at (`transports[]`) | Sheet load room | Result |
| --- | --- | --- | --- | --- |
| 47027 | Krrlytstalarryn, the ancient red dragon | 619771 | 619771 Swamp of Chief Blood-Eye | same pad |
| 47015 | Corrosyvile, the ancient black dragon | 576577 | 576577 The Isle of Undeath | same pad (renamed) |
| 47016 | a huge wyvern | 606262 Bloodstone Keep | 635756 Quietus Quay | **moves** |
| 47017 | a mailed wyvern (Storm Port crest) | 635756 Quietus Quay | 588326 Storm Port | **moves** |
| 47018 | an armored wyvern (Bloodstone Keep banners) | 588326 Storm Port | 606262 Bloodstone Keep | **moves** |
| 47019 | a great white hippogriff | 545407 Venan'Trut | 514072 Myrabolus | **moves** |
| 47020 | a great white griffin | 580080 Torrhan (2nd pad) | 582084 The City of Torrhan | **moves** |
| 47021 | a huge griffin | 543701 Ugta | 543701 Ugta | same pad (renamed) |
| 47022 | a flying carpet | 514072 Myrabolus | 545407 Venan'Trut | **moves** |
| 47023 | Azerathrax, the ancient blue dragon | 622276 Sarmiz'Duul | 564319 Fort Boyard | **moves** |
| 47024 | a large wyvern | 563522 Fort Boyard (old pad) | 622276 Sarmiz'Duul | **moves** |
| 47025 | a harnessed roc | 582084 Torrhan | 519043 Fort Khoralator | **moves** |
| 47026 | a harnessed griffin | 522247 Helgor Outpost | 543662 Kimordril | **moves** |
| 47028 | a harnessed frost drake | 519043 Fort Khoralator | 522247 Helgor Outpost | **moves** |
| 47029 | a harnessed wyvern | 631413 Clan Shatter Stone | 631413 Clan Shatter Stone | same pad (renamed) |
| 47030 | Cryoss, the ancient white dragon | 543662 Kimordril | 514279 Bone Fort Inn | **moves** (new stop) |
| 47031–47041 | 11 new mobs | never spawned | new stops (see sheet) | **missing** |

Visible in game today:

- The "mailed wyvern" whose flanks bear "the gale-crest of Storm Port" (47017) serves Quietus Quay.
- The "armored wyvern" with Bloodstone Keep banners (47018) serves Storm Port.
- Cryoss (47030) serves Kimordril.

The new plan retires two pads:

- **580080**, the second Torrhan pad used by the Venan'Trut network.
- **563522**, the old Fort Boyard departure pad. Arrivals already landed at 564319, the new Fort Boyard pad.

## Data verification

I checked every sheet value against the world the server actually builds, `areas/world.wld`, using read-only scripts. [`areas/AREA`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/areas/AREA#L412) builds `surface`. The stale copies `newbiemaps.wld` and `surface2011-temp.wld` also define some of these vnums, but they are not built.

- **All 27 load rooms and all 3 Extra Destination rooms exist.** All are in zone #5000 (`surface.wld`).
- **Every pair of stops is reachable by air.** I checked all 351 pairs under the exact `VALID_FLYING_EDGE` rule, with 0 failures. `surface.zon` has no `D` resets, so no surface exit starts out blocked.
- **Distances.** The shortest hop is **12 rooms** (Fort Khoralator ↔ Helgor Outpost). The median is **201**, the mean **199.9** and the longest **379** (Sarmiz'Duul ↔ Kimordril). 15 pairs are 60 rooms or less, and 40 pairs are 300 or more.
- **Path length vs. map distance.** For every pair, the flight path length is within 3 rooms of the wrap-around Manhattan distance on the 400×400 grid, so pricing by path length or by coordinates gives the same result. A coordinate formula **must take the shorter way around each axis**, because many shortest flights cross the edge of the map.
- **Pads sit at their towns.** Most load rooms are 1–6 rooms from the matching zone's map entrance (see the table below).
- **Storm Port Stronghold (637082) is correct.** It is directly south of 636682, the map room that zone #226 "Storm Port Stronghold" (`spshold`) connects to. That zone is 166 flight rooms away from Storm Port itself.
- **Manshaka (634060) has no town in the game yet.**
  - The Manshaka rooms live in `areas/wld/dalvik.wld` ("Dalvik's Dockyard").
  - That file is **not in `areas/AREA`**.
  - It still uses placeholder vnums #1–#476, which collide with existing rooms (for example, #1 is Limbo).
  - Its only map link is Dalvik's Bay → 635660, at (60,339). That is 4 rooms from the Manshaka pad at (60,335).
  - Until the zone is renumbered and added to the build, a Manshaka flight lands on "A Tropical Sandy Beach" in Khomani-Khan with no town nearby.
- **The shipyard ports are real.** Thur'Gurax, Fenaline and Canderthal Harbor are ports in the Ship Yards zone (`shipy`, #431). Their rooms are "Thur'Gurax Port" 43141+, "Fenaline Shipyard" 43181+ and "Canderthal Harbor" 43101+. Each pad is 1–2 rooms from a Ship Yards map entrance.
- **Destination names are labels, not room titles.** Chief Blood-Eye is a region on the map ("The Foul Bog of Chief Bloodeye"; 2,759 map rooms carry Bloodeye names), not a zone. The Isle of Undeath is also a map region. For example, 619771's room title is "A Rugged and Barren Hillside".
- **Every flight mob stays put.** All 27 are `ACT_SENTINEL` and none has `ACT_SPEC`. The proc is attached in code, and the service only answers while the mob is in its origin room.
- **No flight mob has a `.qst` entry,** although the sheet marks 7 named dragons `Quest? = Y` (see the open questions).
- **No stop blocks EXP.** None of the 27 stops is `ROOM_SAFE`, `ROOM_GUILD` or `ROOM_ARENA`, so `gain_exp()` will not zero a discovery reward there. The only flags present are Kimordril's `ROOM_NO_TELEPORT` and Fort Boyard's `ROOM_DOCKABLE`.

<details>
<summary>Stop coordinates, room titles and nearest town entrance</summary>

| Mob | Destination | Pad room | (x, y) | Room title | Nearest matching zone entrance |
| --- | --- | --- | --- | --- | --- |
| 47027 | Swamp of Chief Blood-Eye | 619771 | (171, 299) | A Rugged and Barren Hillside | Map region (The Foul Bog of Chief Bloodeye). Valley of the Snow Ogres (`snogres`) entrance is 36 rooms away |
| 47015 | The Isle of Undeath | 576577 | (177, 191) | An Ominous Landing | Map region (Lifeless Plains of Dead Rising, Jungle of the Living Dead). No zone entrance within 6 rooms |
| 47016 | Quietus Quay | 635756 | (156, 339) | A Marshy Clearing with Patches of Tanglebush | `quietus` #17, 1 room |
| 47017 | Storm Port | 588326 | (326, 220) | Rugged Grasslands Along the Coast | `stormport` #224, 3 rooms (south gate 22401) |
| 47018 | Bloodstone Keep | 606262 | (262, 265) | A Rocky Climb Along the DarkPeak Mountains | `bs` #740, 3 rooms |
| 47019 | Myrabolus | 514072 | (72, 35) | Northern Valley of Myrabolus | `mira` #825, 3 rooms |
| 47020 | The City of Torrhan | 582084 | (84, 205) | Endless Plains of Grassy Pastures | `torrhan` #666, 6 rooms |
| 47021 | Ugta | 543701 | (101, 109) | Endless Plains of Grassy Pastures | `ugta` #391, 4 rooms |
| 47022 | Venan'Trut | 545407 | (207, 113) | The Amber Sands of an Island Desert | `desert` #490, 13 rooms |
| 47023 | Fort Boyard | 564319 | (319, 160) | A Beach of Fine Sand | `fortb` #381, 6 rooms |
| 47024 | Sarmiz'Duul | 622276 | (276, 305) | Vast Grasslands Within the DarkPeak Valley | `sarmiz` #94, 2 rooms |
| 47025 | Fort Khoralator | 519043 | (243, 47) | A Spacious Mountain Clearing | `alatorin` #831, 1 room |
| 47026 | Kimordril | 543662 | (62, 109) | A Rocky Mountain Clearing | `kimordril` #955, 1 room |
| 47028 | Helgor Outpost | 522247 | (247, 55) | A Mountain Clearing | `alatorin` #831, 1 room |
| 47029 | Clan Shatter Stone | 631413 | (213, 328) | A Small Covered Mountain Outpost | `kvarkpass_connector` #546, 1 room |
| 47030 | Bone Fort Inn | 514279 | (279, 35) | The Frozen Grassland of the Northern Tundra | `tundra` #137, 1 room (Bone Fort Inn rooms 13712+) |
| 47031 | Winterhaven | 533479 | (279, 83) | Lush Plains of Shrubs and Small Bushes | `wh` #550, 1 room |
| 47032 | Shady Grove | 584293 | (293, 210) | Rugged Hillside of the Northern Wilds | `shady` #975, 1 room |
| 47033 | Tharnadia | 570024 | (24, 175) | A Recently Rebuilt Stone Highway | `tharnadia` #1325, 1 room |
| 47034 | Fenaline | 529229 | (29, 73) | The Lowlands of a Coastal Rim | `shipy` #431 (Fenaline Shipyard 43181+), 2 rooms |
| 47035 | Canderthal Harbor | 546144 | (144, 115) | A Sloped and Rocky Hillside | `shipy` #431 (Canderthal Harbor 43101+), 2 rooms |
| 47036 | Nizari | 575328 | (128, 188) | Sand Dunes of the Calimshan Desert | `nizari` #400, 1 room |
| 47037 | The Jade Empire | 641295 | (95, 353) | The Jade Hills | `jademini` #772, 3 rooms; `jade` #766, 6 rooms |
| 47038 | Manshaka | 634060 | (60, 335) | A Tropical Sandy Beach | **None built.** `dalvik` is not in `areas/AREA`; its Dalvik's Bay link at 635660 is 4 rooms away |
| 47039 | Varathorn Keep | 577835 | (235, 194) | Rocky Foothills of the Black Mountains | `kastle` #994, 4 rooms |
| 47040 | Thur'Gurax | 616547 | (147, 291) | The Dreary and Rocky Hillside of Chief Bloodeye | `shipy` #431 (Thur'Gurax Port 43141+), 1 room |
| 47041 | Moonshae Island | 557220 | (20, 143) | The Gentle Rolling Hills of Moonshae Island | `moonshae` #262, 2 rooms |

</details>

<details>
<summary>Flight distance matrix: rooms flown between every pair of stops (columns are the last two digits of the mob vnum, 470xx)</summary>

```text
                                  27  15  16  17  18  19  20  21  22  23  24  25  26  28  29  30  31  32  33  34  35  36  37  38  39  40  41
47027 Swamp of Chief Blood-Eye     - 114  55 234 125 235 181 260 222 284 111 220 299 232  71 244 292 211 271 316 211 154 130 147 169  32 307
47015 The Isle of Undeath        114   - 169 177 159 261 107 158 108 173 213 210 197 206 173 258 210 135 169 266 109  52 244 261  61 130 205
47016 Quietus Quay                55 169   - 289 180 180 206 225 225 339 154 195 264 207  68 219 267 266 296 261 188 179  75 100 224  57 332
47017 Storm Port                 234 177 289   - 109 331 173 286 225  67 135 255 247 243 221 231 183  43 143 250 286 229 302 249 116 250 171
47018 Bloodstone Keep            125 159 180 109   - 360 238 317 207 159  54 201 353 205 112 187 199  86 249 356 268 211 255 268  98 141 277
47019 Myrabolus                  235 261 180 331 360   - 182 103 213 278 326 183  84 195 248 193 241 351 188  81 152 209 105 112 322 219 160
47020 The City of Torrhan        181 107 206 173 238 182   - 113 215 210 292 317 118 313 252 365 317 193  90 187 150  61 159 154 162 149 126
47021 Ugta                       260 158 225 286 317 103 113   - 110 233 371 204  39 200 293 252 204 293 143 108  49 106 162 215 219 228 115
47022 Venan'Trut                 222 108 225 225 207 213 215 110   - 159 261 102 149  98 191 150 102 183 245 218  65 154 272 325 109 238 217
47023 Fort Boyard                284 173 339  67 159 278 210 233 159   - 185 189 194 177 271 165 117  73 120 197 220 219 369 316 118 300 118
47024 Sarmiz'Duul                111 213 154 135  54 326 292 371 261 185   - 175 379 179  86 133 181 112 275 321 322 265 229 214 152 143 303
47025 Fort Khoralator            220 210 195 255 201 183 317 204 102 189 175   - 243  12 149  48  72 213 309 212 167 256 242 295 155 252 273
47026 Kimordril                  299 197 264 247 353  84 118  39 149 194 379 243   - 239 332 257 209 267 104  69  88 145 189 176 258 267  76
47028 Helgor Outpost             232 206 207 243 205 195 313 200  98 177 179  12 239   - 161  52  60 201 297 200 163 252 254 307 151 264 261
47029 Clan Shatter Stone          71 173  68 221 112 248 252 293 191 271  86 149 332 161   - 173 221 198 342 329 256 225 143 160 156 103 378
47030 Bone Fort Inn              244 258 219 231 187 193 365 252 150 165 133  48 257  52 173   -  48 189 285 188 215 304 266 281 203 276 249
47031 Winterhaven                292 210 267 183 199 241 317 204 102 117 181  72 209  60 221  48   - 141 237 160 167 256 314 329 155 324 201
47032 Shady Grove                211 135 266  43  86 351 193 293 183  73 112 213 267 201 198 189 141   - 163 270 244 187 341 292  74 227 191
47033 Tharnadia                  271 169 296 143 249 188  90 143 245 120 275 309 104 297 342 285 237 163   - 107 180 117 249 196 208 239  36
47034 Fenaline                   316 266 261 250 356  81 187 108 218 197 321 212  69 200 329 188 160 270 107   - 157 214 186 169 315 300  79
47035 Canderthal Harbor          211 109 188 286 268 152 150  49  65 220 322 167  88 163 256 215 167 244 180 157   -  89 211 264 170 179 152
47036 Nizari                     154  52 179 229 211 209  61 106 154 219 265 256 145 252 225 304 256 187 117 214  89   - 198 215 113 122 153
47037 The Jade Empire            130 244  75 302 255 105 159 162 272 369 229 242 189 254 143 266 314 341 249 186 211 198   -  53 299 114 265
47038 Manshaka                   147 261 100 249 268 112 154 215 325 316 214 295 176 307 160 281 329 292 196 169 264 215  53   - 316 131 232
47039 Varathorn Keep             169  61 224 116  98 322 162 219 109 118 152 155 258 151 156 203 155  74 208 315 170 113 299 316   - 185 236
47040 Thur'Gurax                  32 130  57 250 141 219 149 228 238 300 143 252 267 264 103 276 324 227 239 300 179 122 114 131 185   - 275
47041 Moonshae Island            307 205 332 171 277 160 126 115 217 118 303 273  76 261 378 249 201 191  36  79 152 153 265 232 236 275   -
```

</details>

### Builder-side data nits

- **47038 name.** The sheet says "a great white giant eagle"; the mob file says "a mighty great eagle".
- **47041 name.** The sheet says "Glimmyris, the great faerie dragon"; the mob file says "Glimmyris, the ancient faerie dragon".
- **47015 description.** It was renamed "Corrosyvile, the ancient black dragon", but its detailed description still describes the old skeleton ("This massive skeleton is that of a dragon…"). The skeletal-dragon role now belongs to 47039 at Varathorn Keep.
- **47018 typo.** The long description says "adnored".
- **47034 ANSI name.** `&+cFenaline` has no closing `&N`. Output code should always terminate names anyway.
- **Extra Destination price changes.** The Snow Ogres cavern (620606) goes from 50p to **100p**. The Desolate Island (579365) goes from 200p to **100p**. Storm Port → Stronghold is new: 10p, level 1+.

## Requested behavior

1. **Destination catalog.** The 27 stops from the sheet. Each has a mob vnum, a pad room, a destination name and an ANSI name.
2. **Learning.**
   - New characters know no destinations.
   - The first `list` at a flight mob adds that mob's destination, with a message.
   - The list persists across logout, reboot and copyover.
3. **`list` at a flight mob** shows:
   - every known destination except the current one, priced by distance from this stop;
   - this mob's Extra Destinations: one-way, fixed price, level-gated, as today.
4. **Buying and flying.** `buy <n>` buys a ticket for that entry. `give ticket <mob>` flies there, as today.
5. **Discovery EXP.** Each newly learned destination awards EXP. The amount grows with how many destinations the character has found (roughly +10k per step; see below).

## Implementation notes

### Catalog and paths

- **Replace the two tables.** A destination catalog plus an Extra Destination table replaces `transports[]` and `transport_routes[]`. Static tables in `transport.c` match current practice; the ferries are also a [static table in `ferryact.c`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/ferryact.c#L131-L193).
- **Paths: one search per stop, not one per route.** 27 stops make 702 directed pairs. The current per-route [`dijkstra()`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/graph.c#L1341) allocates two vectors the size of `top_of_world` on every call and explores outward until it reaches the target. Instead:
  - run **one single-source search per stop** at boot (27 searches);
  - use plain BFS, because every edge costs 1;
  - store the direction list for each destination; the return trip is the reverse;
  - or compute paths lazily and cache them.
  - Keep logging and dropping any unreachable pair, as today.
- **Mob route state.** `TRANSPORT_ROUTE(mob)` (npc `value[2]`) is an index into `transport_routes[]` today. It needs to identify the destination (or the origin/destination pair) instead, with the path looked up from the origin's table.

### Pricing

- **Distance** = rooms flown, or the wrap-aware Manhattan distance; they agree to within 3 rooms.
- **Currency.** The current code stores platinum and charges `cost * 1000` coins (`coin_stringv(cost * 1000)`).
- **The formula is Fotenak's decision.** Some illustrative linear rates:

| Rate | 12 rooms (shortest) | 201 rooms (median) | 379 rooms (longest) |
| --- | --- | --- | --- |
| 0.10 p/room | 1p | 20p | 38p |
| 0.25 p/room | 3p | 50p | 95p |
| 0.50 p/room | 6p | 100p | 190p |

  A minimum fare and a rounding rule are probably needed, since the shortest hop is only 12 rooms.

### Tickets

- **Store what the ticket is for, not a table position.** The ticket should record the **destination** (catalog id or destination room vnum) and the origin mob vnum.
- **Validate on `give`.** The ticket's origin must be this mob, and its destination must be valid from this origin.
- **Hardening while in here:**
  - `flying_transport_cmd_give` trusts `ticket->value[7]` with no range or origin check ([L540](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L540)).
  - Both movement events index `transport_routes[]` with only a `< 0` check ([L641](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L641), [L750](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/transport.c#L750)).
  - Tickets are `ITEM_NORENT` (extra flags `8388616` = `NORENT | NOSELL`), and player snapshots leave NORENT items out ([L328](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/player/player_snapshot_capture.c#L328), [L691–L696](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/player/player_snapshot_capture.c#L691-L696)). So stale tickets shouldn't survive a relog or reboot.
  - Even so, a ticket held across a hot table change, or edited by an immortal, can currently point anywhere.

### Per-character persistence ("learned destinations")

There are two options:

- **(A) A new player component in the revisioned player snapshot.** This follows the small per-player sets `PLAYER_COMPONENT_LANGUAGES` and `PLAYER_COMPONENT_INTRODUCTIONS` ([`player_revision_state.h` L12–L25](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/player/player_revision_state.h#L12-L25)). The learned set then travels in the same revisioned player snapshot as the EXP it triggers. **Recommended.**
- **(B) A table like `player_recipes`.** It would hold (`pid`, destination) and be written immediately with `INSERT IGNORE` when learned ([`sql_player.c`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/sql/sql_player.c#L3778-L3800)). It also needs a flat-file repository for `__NO_MYSQL__` builds, like `flatfile_recipe_repository`.

A new table must be registered everywhere `player_recipes` is:

- an immutable migration under `migrations/immutable/` (additive, guarded, re-runnable), plus `migrations/migration_manifest.json`;
- `migrations/runtime_compatibility_manifest.json` and [`src/core/runtime_compatibility_contract.h`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/core/runtime_compatibility_contract.h) (table list and count);
- `migrations/data_lifecycle_manifest.json` (export rule, season action, retention);
- the pwipe ([`sql.c` L4990–L5000](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/sql/sql.c#L4990-L5000)) and [`sql_verify_pwipe_manifest()`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/sql/sql.c#L4371);
- character deletion's [`pid_deletes`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/sql/sql_player.c#L5545-L5564);
- personal-data export and erasure;
- the flat-file mode;
- the bootstrap schema files.

Also decide what a pwipe does to learned destinations. `player_recipes` uses `season_action: reset_delete`.

### Discovery EXP

**Schedule.** Reading "+10k for each" and "goes up with the more you find" as *reward for the n-th destination = 10,000 × n*:

| Destinations found | Reward for that one | Running total |
| --- | --- | --- |
| 1st | 10,000 | 10,000 |
| 5th | 50,000 | 150,000 |
| 10th | 100,000 | 550,000 |
| 16th | 160,000 | 1,360,000 |
| 20th | 200,000 | 2,100,000 |
| 27th (all) | 270,000 | 3,780,000 |

Read as a flat 10k each instead, all 27 destinations give 270,000.

**Grant path.** Quest rewards go through [`gain_exp(ch, NULL, amount, EXP_QUEST)`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/limits.c#L1156) ([`quest.c` L303–L315](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/quest.c#L303-L315)). That path changes the amount in several ways:

- the race factor (`exp.factor.<race>`: e.g. Human 1.3, Orc 1.15, Lich and Illithid 0.1) ([L1516–L1527](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/limits.c#L1516-L1527));
- Rested ×1.5 or Well-rested ×2 ([L1221–L1230](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/limits.c#L1221-L1230));
- the `DIFFICULTY_EXP_EARNED` dial ([L1533](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/limits.c#L1533));
- a **cap of 1/3 of the next level per gain** ([L1542–L1544](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/limits.c#L1542-L1544));
- no gain at all once current EXP reaches 2× the next level ([L1557–L1566](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/limits.c#L1557-L1566));
- nothing in arena, `ROOM_SAFE` or `ROOM_GUILD` rooms ([L1179](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/limits.c#L1179)), though none of the stops are;
- immortals get nothing.

**What the 1/3 cap does to 10k × n**, from [`exp.required.*`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/lib/duris.properties#L724-L736), before race, rested and difficulty modifiers. Level-ups are capped at `exp.maxExpLevel=50`.

| Level | Next level needs | Max per gain | 10k × n passes uncapped | 10k as % of that level |
| --- | --- | --- | --- | --- |
| 1–4 | 2,000 | 666 | never | 500% |
| 5–9 | 8,000 | 2,666 | never | 125% |
| 10–14 | 25,000 | 8,333 | never | 40% |
| 15–19 | 100,000 | 33,333 | n ≤ 3 | 10% |
| 20–24 | 400,000 | 133,333 | n ≤ 13 | 2.5% |
| 25–29 | 1,600,000 | 533,333 | all 27 | 0.62% |
| 30–34 | 3,000,000 | 1,000,000 | all 27 | 0.33% |
| 35–39 | 6,000,000 | 2,000,000 | all 27 | 0.17% |
| 40–44 | 12,600,000 | 4,200,000 | all 27 | 0.08% |
| 45–49 | 20,000,000 | 6,666,666 | all 27 | 0.05% |
| 50 | 40,000,000 | 13,333,333 | all 27 | 0.03% |

A flat amount is huge for new characters (and gets capped) and negligible from level 30 on. Quest EXP rewards are capped at **1/10 of the next level** per reward ([`quest.c` L311–L314](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/quest.c#L311-L314)), so a level-relative formula may fit better. That is Fotenak's call.

**Grant it exactly once per character per destination, even across a crash.** Either save the learned destination first and grant EXP only after that succeeds, or commit both in one revisioned save (option A). Log it the way quest rewards are logged (`statuslog`, and `sql_log(..., QUESTLOG, ...)`).

**Telemetry.** `EXP_QUEST` reports as source `quest`, reason `earned`. A dedicated `EXP_*` type would also need changes to [`progression_source_for_type()` / `progression_reason_for_type()`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/src/world/limits.c#L604-L643) and a new `telemetry_progression_source` value.

### UX and text

- **Learn message.** Something like "You have learned the flight destination: <ANSI name>!", followed by the EXP line.
- **List formatting.** Pad the ANSI names (`pad_ansi`). Keep the numbering identical between `list` and `buy`. Pick a sort order (see the open questions).
- **Sign.** [Sign 420](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/areas/obj/heavens.obj#L4427-L4444) currently reads "Type 'list' when carrier is present to see available routes." Update it to mention learning destinations.
- **Help.** There is **no help entry** for the flight service today. Add one, e.g. `help flight paths`.

### Recovery and copyover

- Keep the `transport_snapshot` meaning: origin and destination room vnums. Then copyover v13 and Redis `TRN1` need no format change; `transport_restore()` simply resolves the pair through the new model.
- Moved mobs are already handled: a snapshot whose origin no longer matches is landed at the new home.
- Update `docs/operations/WORLD_SINGLETON_RECOVERY.md`.

## Tests

- **Existing singleton test.** [`tests/async/test_world_singletons.py`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/tests/async/test_world_singletons.py#L9-L11) compiles slices of `transport.c` cut at the markers `// Handles list command` and `int do_simple_move_skipping_procs`. Keep those markers or update the slicing.
- **Existing harness.** [`tests/async/world_singletons_harness.cpp`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/tests/async/world_singletons_harness.cpp#L381-L398) hard-codes the current table: rooms 543662/519043 and mobs 47030/47028. It also sets [`TRANSPORT_ROUTE(flight) = 16`](https://github.com/Community-Duris/Duris/blob/a71fdfee7782f15760a95dc9731969adc70e7cb8/tests/async/world_singletons_harness.cpp#L507-L513), which is Kimordril → Fort Khoralator. Update both for the new catalog.
- **New focused tests:**
  - catalog validation: every pad exists, all pads are in one zone, every pair is reachable;
  - the price function;
  - learn-on-`list` is idempotent, and the EXP is granted exactly once, including across a simulated crash and replay;
  - ticket validation: wrong origin, unknown destination, out-of-range values;
  - a persistence round trip in SQL and flat-file modes;
  - pwipe, deletion and export coverage for the new table or component.
- **Gameplay journey** with the test account: learn two stops, fly between them, check the price and the EXP, relog, and confirm the list persisted.

## Suggested phasing

1. **Catalog and pricing.** The catalog, per-stop paths, distance pricing, destination-based tickets and Extra Destinations, with every destination visible and nothing persisted yet. This also fixes the placement drift.
2. **Learned destinations.** Persistence plus learn-on-`list`.
3. **Discovery EXP.**
4. **Help, sign text and docs.**

A stopgap that only realigns `transports[]` with the mob file is possible, but on its own:

- it strands Cryoss (47030) at Bone Fort Inn, which has no routes;
- the Fort Boyard route still departs from 563522, not the new 564319 pad;
- the Venan'Trut ↔ Torrhan leg still uses the retired 580080 pad.

It is better folded into phase 1.

## Open questions for Fotenak

1. **Price formula.** Rate per room, minimum and maximum fare, rounding. Are Extra Destination costs in platinum?
2. **EXP schedule.**
   - Does the n-th destination give 10k × n, or a flat 10k?
   - Should it scale with level instead, given the 1/3-level cap and how small 10k is past level 30?
   - Do the Rested bonus and race factors apply?
3. **What does `Quest? = Y` mean** for the 7 named dragons: Krrlytstalarryn, Corrosyvile, Azerathrax, Cryoss, Aurumax, Verdax and Glimmyris? Do they need dialogue or quest entries in `vehicles.qst` (none exist today)? Or should their destination be earned through a quest rather than by typing `list`?
4. **Restrictions.**
   - The old table gated the Venan'Trut network at levels 46/47 and the two one-way specials at 51. The sheet has no level, race or racewar limits on network destinations. Is every destination open to everyone, including flights into the other side's cities?
   - Should immortals see every destination?
5. **Manshaka.** Hide it until Dalvik's Dockyard is renumbered and added to `areas/AREA`, or ship the landing now?
6. **Persistence scope.** Per character (assumed)? Reset at pwipe, like recipes?
7. **`list` display.**
   - Unknown destinations: hidden (assumed) or shown as locked?
   - Sort order: by distance, alphabetical, or sheet order?
8. **Known-destinations command.** Should players be able to see their destinations anywhere (e.g. a `flights` command), or only at a flight mob?
9. **Canonical names** for 47038 and 47041 (sheet vs. mob file), and the 47015 description.
10. **Retirements and prices.** Confirm retiring the 580080 (Torrhan) and 563522 (Fort Boyard) pads, and the new Extra Destination prices.
11. **"Behemoth Herders".** The "old routes" tab ends with a row that names only "Behemoth Herders". It has no mob, rooms or price, and it is not in the new tab. That zone exists and is built: #943 `herders`, "The Behemoth Herders", entered from map room 594610 at (210, 236). The flight code has never referenced it. Is it a planned destination that still needs a mob and a pad?

## References

- **Builder commits:** `0fa96b480`, reverted in `1538cfcc4`, re-landed in `4ee13487a`. The original flight routes date to 2009 (`6a70c4453`, `0f076dd24`, `937300728`).
- **Related issues:** #615 (the Stromvok ferry, from the same builder update), #235 and #315 (flight dragon singleton recovery).
- **Main code:** `src/world/transport.c`, `src/world/transport.h`, `src/world/graph.h`, `src/world/graph.c`, `src/world/limits.c`, `src/world/quest.c`.
- **World files:** `areas/{mob,obj,wld,zon,qst}/vehicles.*`, `areas/obj/heavens.obj` (sign 420), `areas/wld/surface.wld`, `areas/wld/dalvik.wld`.
````

#### Comment 1 of 2: `moshehbenavraham`, 2026-09-22

https://github.com/Community-Duris/Duris/issues/616#issuecomment-5786076560

````markdown
Cross-reference: #615 is the other request from the same vehicles-area update, the Stromvok ferry. It's on [`enhancement/615-stromvok-ferry`](https://github.com/Community-Duris/Duris/tree/enhancement/615-stromvok-ferry).

The two changes don't overlap in code. Ferries come from `ferries[]` in `ferryact.c`, and flight mobs come from `transports[]` and `transport_routes[]` in `transport.c`. Vnum 47018 appears in both, but in separate vnum spaces. **Object** 47018 is the Stromvok. **Mob** 47018 is a flight mob: `transports[]` spawns it at 588326 today, and this design moves it to Bloodstone Keep (606262).
````

#### Comment 2 of 2: `fotenak`, 2026-09-23

https://github.com/Community-Duris/Duris/issues/616#issuecomment-5797507244

````markdown
1. Price:  20p for a short flight, and 250p seems like a good starting point. 3rd option (0.5 plat per room)

2. Exp Bonus:  lets scale it with the gained exp cap, and allow rested bonus to affect it. No race barriers

3. Quest: Y for the seven named dragons will be a vehicles.qst where they reward player for eliminating the others. (Note: make sure they are killable, leave corpses, etc)

4. Restrictions: lets remove all restrictions to start and let the dynamic ticket pricing be the only wall. Can revisit this later if it becomes problematic.

5. Manshaka:  keep the surface vnum landing pad, but OK to rename the destination "Dalvik's Dockyard" until Manshaka is done being written.

6. Persistence scope:  Yes, per character, reset at pwipe.

7.  List display:  sort by distance! Cool idea!

8. Let them see it from anywhere with "flights" command

9. Canonical names: fixed sheet to match, Corrosyvile description i will expand when I submit the quests part. 

10. Torrhan i moved a few rooms to new pad 582084. **Fort Boyard you are correct this was on the beach, so I moved it back to 563522 on the sheet**

11. Behemoth Herders I was considering as a pad, but ultimately went with nearby Varathorn Keep. Removed from sheet.
````
