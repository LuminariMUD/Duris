# Issue #612: durable Keep and resumable first entry

Status: implementation and local qualification complete. Prerequisites #628, #632, #634, #635, #636, #639 and #640 are merged. [Final PR #641](https://github.com/LuminariMUD/Duris/pull/641) targets master and is ready for review. Updated 2026-11-04.

- Work item: [Duris #612](https://github.com/LuminariMUD/Duris/issues/612).
- GitHub Development branch: [branch/issue-612-kept-character-resume](https://github.com/LuminariMUD/Duris/tree/branch/issue-612-kept-character-resume).
- Local worktree: `/home/aiwithapex/projects/duris-issue-612-kept-characters`.
- Inspected base: `96ef0ed6b1c1e70edf8aaf560712edc322ce70f6`, fetched from `origin/master` on 2026-11-03.
- Method: [ablation](../../.agents/skills/ablation/SKILL.md), applied after tracing current callers, persistence, loading, grants, and tests.
- The #584 flight transport plan is recorded in [issue-584-flight-transport-plan.md](issue-584-flight-transport-plan.md).

## Outcome

A successful **Keep** preserves the chosen character, stats, identity, and account ownership across disconnect, timeout, account relog, and cold restart. The account can select that character and resume the required approval/first-entry steps. First-entry initialization and starter rewards complete once, including after delayed persistence or grants. Before Keep, abandoned attempts leave the name available.

Success means a committed usable baseline, not merely acceptance by the save queue. While persistence is pending, the client sees a saving state; a disconnected client can later find a committed character. A known failed creation leaves no durable partial character and releases only its own reservation after outstanding work is settled. An uncertain commit stays reserved until the existing writer resolves its outcome.

Existing broken records receive a guarded, testable repair/release path. Ownership is never inferred from a name, level, IP, or age alone.

## Non-goals

No production queries, migrations, data repair, server restart, deployment, or bulk deletion in this implementation. Future production repair requires the user's permission and a per-record decision. No rested-bonus policy change, name-expiry service, PID reuse, blanket level-0 cleanup, global save-pipeline rewrite, new persistence backend, or changes to unrelated item-authority work.

#612 stays open until prevention, resumption, recovery capability, and the acceptance journeys below are implemented and proven. Historical #238/#489/#417 and merged item work are context, not additional issues to close.

## Ablation decisions

- **Keep durable/resumable Keep.** The prompt explicitly offers to keep the rolled character, and the issue requests preservation/resumption. Deleting on disconnect would lose that outcome. No expiry timer or periodic reaper is needed.

- **Keep a small pending-save transition and completion hook.** The real distinction is queue acceptance versus commit, including after descriptor loss. Reuse writer ordering, revision checks, load holds, and descriptor/runtime identity. Do not add a service, general workflow framework, second queue, or synchronous MariaDB query on the game loop.
- **Reuse level 0 for first-entry detection, existing accepted-name markers, and existing reward receipts.** Add only the durable approval-pending flag and grant-operation/completion information that cannot be reconstructed safely from these authorities. Do not create a parallel lifecycle database when existing saved flags/snapshot fields suffice.

- **Keep targeted recovery and real socket/restart proof.** Existing source contracts do not cross this failure boundary, and a metadata-only fix cannot release existing unknown-owner rows safely.
- **Drop unrelated cleanup, broad fault infrastructure, global persistence format changes, and automatic orphan attachment/deletion.** Each retained change below closes a traced path or an explicit acceptance criterion. Extend existing fixtures before adding another test runner.

## Implementation sequence

### 1. Reproduce the exact boundary with maintained fixtures

Use the disposable MariaDB runner and the database/environment setup pattern in [test_account_recovery_mysql_journey.py](../../tests/async/test_account_recovery_mysql_journey.py). The fixture must never inherit the checkout's operational database/listener. Supply valid minimal-world/frag-cap prerequisites as fixture data, with nonempty disposable credentials.

Add executable repository and completion-path cases to the existing save/account harnesses for initial owner/mapping, rollback, queue rejection, delay, ambiguous commit, and connection override. Source contracts remain secondary guardrails.

### 2. Establish a complete initial commit

Capture immutable account identity with the initial player snapshot before handing it to the writer; never consult a freed descriptor on a worker. Keep ordinary saves from changing an established owner based on stale account context.

For MariaDB, extend the existing first-save transaction to validate the attempt's PID/name/account, insert the owned active player, save the full usable level-0 snapshot, establish opening baselines, and create the account-character mapping together. A retry of the same attempt must recognize its committed result. Reject conflicting owner/PID/name and deletion tombstones; do not use an upsert that steals or reactivates someone else's character. Preserve account creation counters, projection fields, and existing rename/transfer semantics.

Update snapshot capture/bounds/codec/materialization only as required by the captured account and lifecycle data. Preserve schema-14 and currently supported older snapshot decoding; missing new fields must use verified identity/current legacy approval policy rather than a fabricated owner or a forced reinitialization of entered characters. Update the misleading account-save comment and affected contracts.

### 3. Make Keep, acknowledgment, and cleanup agree

After Y and the final name/admission preflight, reserve the attempt and submit one complete initial baseline for every Telnet branch: ordinary, previously accepted, and approval waiting, in both Chaos modes. Show a saving state while waiting; emit the final Return/approval prompt only after a successful matching commit. WebSocket creation uses the same commit boundary and emits `created` only after it succeeds.

Use a narrow creation completion path in the existing save pipeline, matched by PID/revision and current descriptor/request identity. Pre-entry bodies are absent from `character_list`, so the pipeline's existing `live_player()` search alone is insufficient. Do not retain raw descriptor/body pointers in queued jobs. The generic pipeline currently accepts `stale_revision` as a successful completion; that alone is not proof of initial creation unless the matching committed PID/name/account and usable baseline have been verified.

If disconnected while pending, allow the immutable submitted attempt to complete; committed state remains selectable after relog/restart. On enqueue rejection or a confirmed rollback, unwind only that attempt's in-memory membership/reservation after all submitted work is settled. On ambiguous commit, keep it reserved and let the existing ordered writer retry/read the same identity; neither free the name on timeout nor report success prematurely. Terminal failure after descriptor loss must still reach cleanup. Do not coalesce away initial ownership/approval information before the first commit.

Admission denial after a committed Keep preserves the owned, resumable character and reports the existing denial. Denial before commit leaves no character. Recheck policy before entry, including launch/racewar locks, without discarding a kept character because entry is temporarily unavailable.

### 4. Resume approval and first entry safely

Route a selected owned level-0 character through a shared, small pre-entry continuation used by Telnet and WebSocket. Keep ordinary entered-character login behavior intact. It must restore chosen stats/options, honor stored approval requirements, schedule required kit work, and use the existing `enter_game()` initialization exactly once.

Persist whether this kept attempt is waiting for staff approval using the existing saved flag/status mechanism. A reconnect, transport switch, restart, or later configuration change must not bypass a pending staff decision. Accepted-name/trusted exemptions still apply when Keep decides approval eligibility. Staff approval durably clears the pending requirement before advertising the next step; staff decline cancels/releases only that attempt through the guarded existing deletion path before permitting replacement creation. Test approval followed by disconnect before its save acknowledgment too.

Fix pre-entry connection override so closing an older socket cannot free a body that the new session will reuse. Either transfer a verified pending body without freeing it or close and reload the committed PID; use the existing load hold while a first save/grant is pending. Check account ownership, not only a matching character name. Never attach a replacement descriptor to a stale completion.

Preserve level-zero-to-one initialization and all ten chosen stats. For first-entry kits, reuse existing critical-command receipts and reconciliation, with a durable per-PID binding to the kit operation/completion state so retries resume the same grant. Persist the binding before submission; publish/record completion with the existing transaction facilities. If no suitable existing field stores that binding, add only the narrow metadata this path needs, with MariaDB snapshot compatibility. Do not infer completion merely from a nonempty bag, generate new item UIDs for an already submitted kit, or clear the pending intent before durable completion. Keep existing bank/epic/achievement intents and command blocking. Prove interruption after level-one baseline but before kit completion, as well as active pre-entry kit completion after disconnect.

### 5. Provide guarded recovery for existing broken records

Add a narrowly privileged staff recovery entry point alongside existing character administration, with inspect, explicit attach, and explicit release operations. Reuse `delete_character()`/backend deletion and projection repair; if they require a loadable body, factor only the validated PID/name deletion work needed for an otherwise unloadable orphan. Do not create a second destructive SQL/file-deletion implementation.

Inspection is read-only and identifies PID/name, owner, active/tombstone status, mappings, usable snapshot/domain state, and outstanding save/grant work. Mutation names an exact PID and expected name and revalidates under the backend's transaction/lock/fence. Reject live/pending actors, conflicting owners, renamed/replaced identities, established/approved legitimate characters, and unproven safety conditions.

- **Usable snapshot, demonstrable owner, missing mapping:** repair owner/membership atomically, preserving stats, balances, rewards, approval, and PID; then load through the account normally.
- **NULL/empty owner, usable snapshot:** require staff to supply a verified account with external incident/ownership evidence before attach. Never auto-guess. If evidence cannot establish ownership, leave unchanged or perform a separately authorized explicit release.
- **Membership without a usable snapshot:** distinguish genuine absence from I/O/corruption/pending write. Restore only from an existing verified recovery after-image; never manufacture lost stats. Otherwise report that restoration is impossible and require explicit release of the exact broken attempt.
- **Release:** settle/fence already submitted work first, use existing deletion/tombstone semantics, then forget the live name index only after durable success. Prove a delayed save or grant cannot resurrect the released PID or affect a new claimant of the name.

Add `docs/operations/kept-character-recovery.md` with the exact inspected fields, staff commands, ownership-evidence requirement, dry inspection examples using synthetic data, retry/refusal behavior, and postconditions. That file is an implementation deliverable. No production player/account identifiers belong in commits. The issue's additional ownerless row remains an unverified candidate until its current state is inspected with permission.

### 6. Complete acceptance across the real paths

On MariaDB, run the basic post-Keep/pre-entry disconnect/resume/restart journey for all eight combinations of ordinary/already-accepted name, approval off/on, and Chaos off/on. Where an accepted marker exempts approval, assert the exemption explicitly. Use synthetic names/accounts/accepted markers and restore fixture state between cases.

Every issue acceptance item has these concrete proofs:

- **Before Keep, N/Q, final Return, timeout, normal entry:** no allocation/reservation on pre-Keep disconnect/N/Q; owned selectable baseline after committed Keep disconnect; no orphan on the actual final-prompt idle close. Use a fixture clock/state hook to reach the existing timeout threshold, not a changed production timeout or a source-text assertion. Check ordinary entry and relog as controls.
- **Resumable choices/approval/grants:** compare all ten saved numeric stats and race/class/sex/hometown/options before and after disconnect/restart. Pending approval remains pending; staff accept/decline has the intended durable effect. Complete first entry, disconnect again, and show one initialization/kit and unchanged bank/epic/achievement totals.
- **Persistence boundaries:** hold the writer, disconnect before and after commit/acknowledgment, then release it; also queue rejection, terminal rollback, connection loss/ambiguous commit, and restart during publication. Inspect both storage and fresh account selection, including a second session overriding a pre-entry descriptor.
- **Admission/kit boundaries:** force Telnet and WebSocket admission rejection after allocation, and after a successful Keep commit. Delay an active Chaos grant past disconnect; resume/restart without duplicate/lost items, dangling objects, or stale body access.
- **Competition/retry:** two accounts reach Keep for the same case-insensitive name; only one owns a usable character. A losing/failed attempt cannot release the winner's name or alter its mapping. A confirmed failed/released attempt permits safe reuse by a new PID; approved pending and entered controls survive.
- **Recovery:** seed ownerless snapshot, known-owner missing mapping, membership-without-snapshot, tombstone/conflicting owner, and pending-save/grant fixtures. Exercise actual staff inspection/attach/release dispatch, repeat safely, force rollback, verify account loading and live name availability immediately and after restart.

Keep assertions on durable row/catalog/domain state, account selectability, name-index checks, and receipt/item counts. A helper test or `validate_name` response alone cannot prove the complete outcome. Use the existing WebSocket client/stat journey helpers for protocol coverage. Include one full-world ordinary Telnet and one Chaos/WebSocket resume journey to expose fixture-only assumptions.

## Files

Expected implementation areas, each justified by a traced boundary:

- `src/account/nanny.c`, `src/account/account.c`, `src/account/account.h`, `src/net/ws_handlers.c`: creation commit/continuation, account resumption, safe override.
- `src/player/player_snapshot.h`, `player_snapshot_capture.c`, `player_snapshot_codec.c`, `player_save_pipeline.c` and the corresponding headers under `src/player/`: immutable initial account/lifecycle context and completion handling; `player_load_materialize.c` only for newly stored state.

- `src/player/player_snapshot_repository.c`, `src/sql/sql_player.c`, `src/core/files.c`: initial SQL ownership/membership, safe recovery, existing deletion reuse.
- `src/cmd/actwiz.c` and existing command/prototype registration files: staff approval/decline and scoped recovery dispatch. `src/core/structs.h`/`defines.h` only for necessary pending-state/flag fields.
- `src/item/item_movement_transaction.c` and existing grant/receipt types only where durable kit resumption requires them; retain the existing coordinator.

- `docs/operations/kept-character-recovery.md`, affected creation/recovery help, and this plan's completion evidence.

## Proof commands and completion gates

Run the narrow repository/runtime tests changed in each step first:

```sh
make -C src
python3 tests/async/test_player_snapshot_capture.py
python3 tests/async/test_player_save_pipeline.py
python3 tests/async/test_kept_character_lifecycle.py
tests/async/with_disposable_mariadb.sh python3 tests/async/test_kept_character_journey.py --backend mariadb --server bin/server/dms_new
```

Completion requires every acceptance scenario above, clean changed-line formatting and MariaDB builds, an inspected narrow diff, and recorded exact commands/results. Merging follows the `AGENTS.md` merge gate: the required CI checks green on the exact head commit. Report any missing runtime evidence explicitly and leave #612 open if a required gate is unverified.
