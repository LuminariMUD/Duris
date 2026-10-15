# Zhad's persistent stun: Isha cloak investigation and follow-up plan

Investigated 2026-10-15 against worktree HEAD
`d27e2b5ec5431d6489acd6258c264dcb1aeec29a`, with existing unrelated GUI/telemetry
changes present. Deliverable: investigation and a plan, not a gameplay change.

## Conclusion and corrected interpretation

**Object 135216 directly grants its wearer `AFF2_STUNNED`. It creates no stun
affect record or expiration event.** The equipment continually supplies the flag;
waiting, `restore`, and `affectpurge` do not remove that source. This explains
both Zhad's persistent stun and the accompanying lack of movement regeneration.

The owner relayed former staff's explanation that there are two Isha cloaks and
this version is deliberately cursed, then clarified that being able to use
`remove` while stunned is the intended escape. **The accepted behavior is stun
while worn, with normal removal allowed.** Preserve that behavior; do not remove
the flag, add a timer, or require death. Early working descriptions of a "bad
flag" were premature and are superseded here.

The current removal code matches that interpretation: an otherwise eligible
mortal can remove 135216, and its equipment stun clears. The cloak does not have
`ITEM_NODROP`. Death also clears the equipment source through `make_corpse()` →
`unequip_all()` → `unequip_char()`, but is not required. The isolated native test
verified removal; a full in-game removal journey was not performed by this
investigation. No gameplay repair is indicated by the established behavior.

There is no evidence here of a shared stun-expiration failure causing this
incident. Focused scheduler tests pass, and the actual stun callback clears an
ordinary timed stun in the isolated reproduction. That is evidence for the
tested paths, not a claim that every affect lifecycle is bug-free.

## Object identity and active data

| Property | 135216 | 19916 |
| --- | --- | --- |
| Display name | the black hooded cloak of Isha the Wanderer | a black hooded cloak of Isha the Wanderer |
| Active source | `areas/obj/azhural.obj:129` | `areas/obj/astral_tiamat.obj:233` |
| Area selection | `areas/AREA:388` selects `azhural` | `areas/AREA:102` selects `astral_tiamat` |
| Affect bank 1 | `100`: farsee, sense life, minor globe | `1572864`: sneak and hide; normal equipment application filters hide |
| Affect bank 2 | `268959744`: stunned and flurry | `0`: no stun |
| Affect bank 4 | `0` | `1048576`: hawkvision |
| Native special | No vnum-specific assignment found | `artifact_hide`, shared with other items |
| Relevant extra flags | `69632`: secret and no-identify; no `ITEM_NODROP` | Different flags and stats; not a duplicate of 135216 |

The inactive `areas/obj/tiamats_lair.obj:129` also contains 135216 with the same
numeric definition. **That duplicate source file is not the second distinct
cloak.** The second cloak is vnum **19916**.

The running server reads object prototypes from `areas/world.obj`
(`src/world/db.h:20`). Its record at line 252844 matches the selected Azhural
source, including:

```text
0 0 100 100 268959744 0 0
```

`parse_object_template()` reads weight, cost, condition, then affect banks 1–4:

```text
weight=0 cost=0 condition=100
bitvector1=100 bitvector2=268959744 bitvector3=0 bitvector4=0
268959744 = 268435456 (AFF2_FLURRY) + 524288 (AFF2_STUNNED)
```

See [object parsing](../../src/world/db.c),
[flag definitions](../../src/core/defines.h),
[native assignments](../../src/specs/specs.assign.c), and
[artifact_hide](../../src/specs/specs.object.c). The hiding special on 19916
responds to `say hide`; its inspected body does not apply stun.

## Incident evidence

Times below are UTC on 2026-10-15. The owner confirmed that Zhad had the cloak
equipped and that Reni, Thor, and Zhad were testing the behavior. The local logs
provide this narrower sequence; they do not record every wear/remove operation.

| Time | Observation | Local evidence |
| --- | --- | --- |
| 07:08:37–39 | Reni loads 135216 and gives it to Zhad | `logs/player-log/wizcmds:883` |
| 07:50:07 | Zhad reports apparently permanent stun | `logs/log/chat:183` |
| 07:50:26 | Zhad also reports no movement regeneration | `logs/log/chat:185` |
| 07:50:29 | Reni restores Zhad | `logs/player-log/wizcmds:959` |
| 07:53:47 | Zhad's death is recorded | `logs/log/status:9739` |
| 07:54:19–57 | Transfer, full heal, restore, and level recovery are recorded | `logs/player-log/wizcmds:960` |
| 07:58:06–09 | Reni loads another 135216 and gives it to Zhad | `logs/player-log/wizcmds:966` |
| 07:58:33–50 | Reni and Zhad identify the cloak as the source | `logs/log/chat:190` |
| 08:00:30 | Reni gives a cloak to Zusuk | `logs/player-log/wizcmds:970` |
| 08:04:34–38 | Zhad confirms the stun occurred on wearing the cloak | `logs/log/chat:196` |

The logs record discussion of `affectpurge`, not proof that a particular purge
executed or succeeded. No Zhad-specific missing-short-affect-event diagnostic
was found in the inspected current debug log. Neither absence of a diagnostic
nor the subsequent death independently proves the complete live state.

The inspected server was PID 3429849, started 2026-10-14 17:47:57 UTC, running
`bin/server/dms` from this checkout. `areas/world.obj` was generated at 17:47:56
and had not been rewritten during this investigation. The binary timestamp was
17:43:17; its backend marker was `mariadb/production`. The current worktree is
not claimed to be byte-for-byte identical to that running binary.

## Mechanism, removal, and staff recovery

1. `equip_char()` schedules affect recalculation. `all_affects()` scans worn
   equipment, and `affect_modify()` copies its second affect bank into
   `TmpAffs.BV_2`. `apply_affs()` applies that bank to the wearer.
2. `IS_STUNNED()` tests that flag, regardless of whether it came from equipment
   or a spell. `move_regen()` explicitly returns zero while stunned. No lost
   timer is necessary to explain either symptom.
3. Ordinary `Stun()` instead creates a `SPELL_PWORD_STUN` affect with
   `AFFTYPE_SHORT | AFFTYPE_NOSHOW | AFFTYPE_NODISPEL`. `affect_to_char()` schedules
   `event_short_affect`, whose callback removes the affect.
4. `do_affectpurge()` walks character affect records. With only the cloak's
   flag there is nothing to remove. If a timed stun also exists, removing that
   record still leaves the equipped cloak's flag applied. `restore` recalculates
   affects and refills resources; it does not remove the cloak.
5. `unequip_char()` subtracts the old equipment/affect contribution, detaches
   the item, and reapplies the remaining contributions. The real `remove_item()`
   path succeeds for this cloak on an otherwise eligible mortal with inventory
   space. There is no stun-specific veto in that function, and the inspected
   command/input gates do not impose a general stun ban on `remove`.
6. Death's ordinary corpse path unequips the character. Re-equipping the same
   cloak should reapply its effect; death does not change the item's definition.

Sources: [affect application and timers](../../src/magic/affects.c),
[equipment lifecycle](../../src/world/handler.c),
[remove_item and do_remove](../../src/cmd/actobj.c),
[staff purge and restore](../../src/cmd/actwiz.c),
[movement regeneration](../../src/world/limits.c),
[corpse creation](../../src/combat/fight.c), and
[command gates](../../src/cmd/interp.c).

The operational implication is source-aware recovery: diagnose which cloak is
worn, and distinguish its permanent contribution from a timed spell. Do not
promise that `affectpurge zhad all` cures an equipped curse, or remove all buffs
just to test that hypothesis. No recovery command was sent to a live player by
this investigation.

## Historical corruption and flag-layout hypotheses

The numeric meanings have not recently shifted: the 2011 and 2012 server
definitions already use `BIT_20=524288` for `AFF2_STUNNED` and
`BIT_29=268435456` for `AFF2_FLURRY`, as they do now. The 2012 editor definitions
also agree. Today's editor includes the shared server definitions.

The active Azhural cloak's exact numeric line dates to **2012-08-07** in commit
`50b400005d`. That commit selected the new Azhural area and explicitly mentioned
editor problems between branches. Its server loader already treated the fourth
number as affect bank 1 and the fifth as affect bank 2. Thus the current stun
interpretation is consistent with the checked-in code at introduction; a recent
renumbering is not required. The inactive Tiamat copy acquired the same line in
`8819465524` on 2016-08-15.

There is older format ambiguity, which must not be mistaken for established
intent. The 2011 Tiamat edits `2260c1426` and `d1f230206` included:

```text
0 0 100 268959744 0 0 0
```

That period's loader also consumed a `max_condition` number, whereas the 2012
loader had stopped doing so. Moving `268959744` between affect banks would also
change its meaning: in bank 1 those bits are sneak/awareness; in bank 2 they are
stun/flurry. This is a concrete historical reason to inspect version/format
history if design intent is disputed, **not proof of an accidental conversion**.
The owner's clarified intent is to preserve the curse and permit removal while
stunned. Git history alone cannot establish what an earlier builder intended.

## Wider scope and persistence

A read-only numeric scan of the generated active world parsed **19,149 object
records with no parse failures**. Exactly one vnum, **135216**, supplied the stun
bit. The same scan checked bank-2 holding-breath, memorizing, drowning, casting,
and scribing flags; none were present. This is not a scan of every possible
harmful flag or scripted proc.

Scanning 442 `areas/obj/*.obj` source files parsed 21,631 records and found the
two source copies of 135216. One inactive file, `hostel.obj`, contains malformed
extra tilde delimiters, so that source-file scan is incomplete. It is not
selected in `areas/AREA`; the active-world scan remains complete. Do not alter
that unrelated file as part of this work.

Production SQL was inspected using short read-only transactions. The connection
target matched the live process's database target. At the observation point:

- The ownership ledger recorded two live 135216 identities, associated with
  Zhad and Zusuk.
- No 135216 payload row appeared in the queried player, pet, corpse, saved,
  locker, account-locker, shopkeeper, or siege item tables. No explicit stun bit
  appeared in those tables' queried `bitvector2` columns.
- Zhad had no saved `SPELL_PWORD_STUN` or stun-bit affect row.

These are persisted snapshots, **not live inventory inspection**. Ledger entries
without matching materialized item rows must not be treated as proof of absent
live items, or as an orphan-item defect without examining the save lifecycle.
No player, account, item, or environment data was modified.

If item behavior is later changed deliberately, prototype edits alone may not
update existing copies. [Snapshot capture](../../src/player/player_snapshot_capture.c)
records item flags; [the writer](../../src/player/player_snapshot_repository.c)
persists them explicitly, and [item restoration](../../src/player/player_load_items.c)
applies saved overrides. Any authorized future correction must cover existing
in-memory copies and saved payloads, not just newly loaded prototypes.

## Verification completed

Local investigation artifacts are retained in `bin/analysis/stun-135216/` and
are not source changes. `probe.py` extracts the actual production
`all_affects`, `affect_modify`, `apply_affs`, `Stun`, `affect_to_char`,
`event_short_affect`, `affect_remove`, `do_affectpurge`, `remove_item`, and
`unequip_char` function bodies into an ASan/UBSan executable. Unrelated stat,
logging, persistence, and inventory-transfer dependencies are controlled
fixtures; the probe does not connect to a game server or database.

Passed assertions:

- Wearing the cloak's mask sets stun with zero affect records and zero timers.
- `affectpurge all` and 100 recalculations leave the equipment stun active.
- Actual mortal `remove_item()`/`unequip_char()` succeeds and clears that stun.
- Ordinary stun's actual expiration callback clears its record and stun bit.
- Actual `affectpurge` clears an ordinary timed stun without the cloak.
- Expiring a timed stun while wearing the cloak removes the record but leaves
  the equipment stun.
- A fixture-only control removing the stun bit preserves flurry and prevents
  stun. This is an experiment, **not a proposed content edit**.

Commands and outcomes:

```text
python3 bin/analysis/stun-135216/probe.py                 PASS (ASan/UBSan)
python3 bin/analysis/stun-135216/scan_objects.py          active scan complete
python3 tests/async/test_nevent_scheduler_runtime.py     PASS, all 14 modes
python3 tests/async/test_web_spray.py                    PASS
```

The scheduler suite exercises actual short-affect expiry, cancellation, owner
reuse, player liveness, priority, aging, and catch-up. The Web Spray test covers
related PC/NPC restoration and cleanup with a deterministic scheduler. Neither
substitutes for a full in-game cloak death/relog/copyover journey. The cloak probe
uses a controlled scheduler adapter and explicitly invokes the real expiration
callback. It does not reproduce scheduler time passage itself.

No server restart, deployment, migration, live-player experiment, generated-area
rewrite, or gameplay source edit was performed. A server rebuild is unnecessary
for this documentation deliverable.

## Resolution and optional follow-up

The reported incident is explained by intentional equipment behavior, and the
owner's intended removal rule matches the tested code. There is no open
death-only design question or planned gameplay repair. The following journeys
remain available for additional qualification if requested or if another report
contradicts these findings.

1. **Verify both variants on a disposable full server.** Use a mortal
   with free inventory space, normal posture, no other stun, and no unrelated
   command lag. Record flags, affect records, and pending short-affect events
   before wear, after wear, after waiting, after targeted/all purge, after
   restore, after `remove cloak`, and after rewear. Test 19916 independently,
   including its hiding special. Verify command and movement-regeneration
   behavior, not only the affect list. Do not use Zhad's live character as the
   fixture.

2. **Verify persistence and overlapping affects.** For 135216, exercise normal
   death/corpse recovery, rewear after death, disconnect/reconnect, rent/login,
   reboot/copyover, and transfer to a second mortal. Include a real timed stun
   overlapping the cloak. Distinguish legitimate persistent equipment stun
   from a timed affect missing its event, and verify flags and equipment
   ownership remain consistent. The cloak's contribution must last while worn
   and clear on removal; an independent timed stun retains its own lifetime.

3. **Investigate only a distinct failure.** If stun remains
   after actual removal with no other contributing source, capture character
   flags, every contributing item, matching affect records, event handles and
   due ticks. Then investigate rejected scheduling, premature cancellation,
   load-before-world liveness, save-duration handling, and stale flags. The
   cloak's permanent equipment flag alone is not evidence for changing the
   shared scheduler. Any content checker must allow deliberate curse items;
   the scan does not justify blanket rejection of equipment stun. Any resulting
   code repair needs a focused regression, formatting checks, and a server build.
   Any production rollout or persisted-item repair needs separate authorization
   under `AGENTS.md`; neither is indicated by this incident.
