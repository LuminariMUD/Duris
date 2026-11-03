# Issue #612: durable Keep and resumable first entry

Status: implementation in progress; persistence chunks delivered in open [PR #628](https://github.com/LuminariMUD/Duris/pull/628) → [PR #632](https://github.com/LuminariMUD/Duris/pull/632) → [PR #634](https://github.com/LuminariMUD/Duris/pull/634). No production operation performed. Updated 2026-11-03.

- Work item: [Duris #612](https://github.com/LuminariMUD/Duris/issues/612).
- GitHub Development branch: [branch/issue-612-kept-character-resume](https://github.com/LuminariMUD/Duris/tree/branch/issue-612-kept-character-resume).
- Local worktree: `/home/aiwithapex/projects/duris-issue-612-kept-characters`.
- Inspected base: `96ef0ed6b1c1e70edf8aaf560712edc322ce70f6`, fetched from `origin/master` on 2026-11-03.
- Method: [ablation](../../.agents/skills/ablation/SKILL.md), applied after tracing current callers, persistence, loading, grants, and tests.
- The prior completed #584 plan is preserved verbatim as [issue-584-flight-transport-plan.md](issue-584-flight-transport-plan.md).

## Outcome

A successful **Keep** preserves the chosen character, stats, identity, and account ownership across disconnect, timeout, account relog, and cold restart. The account can select that character and resume the required approval/first-entry steps. First-entry initialization and starter rewards complete once, including after delayed persistence or grants. Before Keep, abandoned attempts leave the name available.

Success means a committed usable baseline, not merely acceptance by the save queue. While persistence is pending, the client sees a saving state; a disconnected client can later find a committed character. A known failed creation leaves no durable partial character and releases only its own reservation after outstanding work is settled. An uncertain commit stays reserved until the existing writer resolves its outcome.

Existing broken records receive a guarded, testable repair/release path. Ownership is never inferred from a name, level, IP, or age alone.

## Implementation handoff / current progress

- **Reproduction established on the inspected base.** Fresh MariaDB and flat-file builds ran the new real-socket `test_kept_character_journey.py`. MariaDB saved the synthetic kept character at level 0 / revision 1 / NULL owner; fresh account login had no selectable character. The flat-file control passed disconnect, account selection and cold restart. Fixture boot uses a disposable migrated schema, nonempty disposable credentials and a valid level-31 `level_cap` seed. It never reads checkout `.env`.
- **Chunk 1: initial MariaDB ownership (locally qualified).** The save pipeline captures the initial account as owned snapshot data while the existing written revision is zero. Such captures include all components, including coalesced captures. The SQL transaction validates the account and exact PID/name/owner/mapping, rejects competing identities and tombstones, then publishes player, membership and opening balances together. A same-attempt retry recognizes a committed baseline without replaying older creation state. Snapshot schema 15 carries the account; supported schemas through 14 decode with an empty creation context. Ordinary saves leave an established owner alone.
- **Ablation refinement:** use existing `written_revision == 0` to retain initial account context until completion; no additional transient baseline flag or synchronous game-loop SQL is needed. The rest of the original acceptance scope remains required. The current journey checks ownership/selectability only; it does not yet claim approval, resumption, delayed acknowledgment, grants or recovery coverage.
- **Git handoff:** [PR #628](https://github.com/LuminariMUD/Duris/pull/628) targets `master` from `branch/issue-612-kept-character-resume`; implementation commit `8bfa04068`. It is ready for review and intentionally does not close #612. No release tag is appropriate for this unmerged feature chunk.
- **Separate fixture repair:** [PR #632](https://github.com/LuminariMUD/Duris/pull/632), `branch/issue-612-claim-fixture`, commit `2ef8057fa`, targets PR #628. A pre-existing compile failure passed bare UIDs to the current typed world-recovery API. The focused fixture-only change supplies complete synthetic floor records. Its save-claim test, build and formatting checks passed. Clean isolated worktree: `/home/aiwithapex/projects/duris-claim-fixture`.
- **Chunk 2 locally qualified:** current worktree is on dependent `branch/issue-612-flatfile-creation`, based on PR #632's `2ef8057fa`. Initial identity, bank/player domains, item claims and usable snapshot are prepared under the existing snapshot → identity → authority lock order and committed through the existing authority journal. New flat-file account-list entries are deferred until baseline acknowledgment so ordinary account saves cannot publish a tentative membership. Existing domain establishment reuses that preparation; obsolete early-publication helpers were removed. No account scalar changes at Keep require an account after-image; the existing account is validated under the same authority fence. Standalone identity readers/mutators recover pending authority after-images before reading or advancing the PID catalog, preventing later recovery from rewinding allocated PIDs. Initial domains retain the captured wallet revision and existing shared bank balances.
- **Chunk-2 Git handoff:** [PR #634](https://github.com/LuminariMUD/Duris/pull/634), `branch/issue-612-flatfile-creation`, implementation `09c5cea98`, targets PR #632 and is ready for review. The primary worktree remains `/home/aiwithapex/projects/duris-issue-612-kept-characters`.
- **Active continuation:** the primary worktree is on `branch/issue-612-creation-ack`, based on #634's documentation handoff `c5b880686`. The first acknowledgment prerequisite is locally qualified: both repositories recognize an exact previously committed initial snapshot even if its account was blocked before reconciliation. A new or newer capture for a blocked account is still refused. Continue with implementation-sequence steps 3–4 below, including pending reservations, UI acknowledgment and resumption; those runtime transitions have not yet changed. Earlier PRs remain ready for review; do not merge them or close #612 as part of this implementation-only handoff.
- **Reconciliation Git handoff:** [PR #635](https://github.com/LuminariMUD/Duris/pull/635), implementation `352e098aa`, targets #634 from `branch/issue-612-creation-ack` and is ready for review. Next work will qualify and fix the pre-entry connection-override lifetime boundary before changing acknowledgment transitions.
- **Takeover qualification:** current worktree is on dependent `branch/issue-612-preentry-override`, based on #635's handoff `83db88576`. The maintained socket journey now tests Telnet and WebSocket takeover of an ordinary kept level-0 character on both backends, compares the same PID and all ten stored base stats before/after first entry, and cold-restarts/relogs again. All four cases pass on existing runtime code. Telnet authentication closes the old same-account descriptor before selection; WebSocket `enter` closes the matching pre-entry descriptor before queuing account confirmation. The source-risk branch in `is_char_in_game()` was not exercised by these normal journeys, so this chunk adds verification rather than a speculative runtime patch. Preserve these controls and requalify the lifetime boundary when the new asynchronous saving state makes additional pre-entry states reachable; the planned PID/owner checks and approval routing remain part of steps 3–4.
- **Next:** implement creation acknowledgment/cleanup, approval/first-entry/grant resumption and guarded recovery on dependent branches. Keep this section current with PR links, exact passing commands and unresolved gates. Neither delivery chunk completes #612.
- Synthetic build/test logs are under ignored `bin/tests/issue-612-*`. Pre-change evidence: `issue-612-before-mariadb.log` and `issue-612-before-flatfile.log`. No credentials, runtime state, generated artifacts or production identifiers are tracked.

Chunk-1 proof (all passed locally on 2026-11-03):

```sh
make -C src -j6
make -C src PERSISTENCE_BACKEND=flatfile BIN_ROOT=../bin/issue-612-flatfile -j6
python3 tests/async/test_player_snapshot_capture.py
python3 tests/async/test_player_item_snapshot_codec.py
python3 tests/async/test_player_save_pipeline.py
python3 tests/async/test_player_save_worker.py
python3 tests/async/test_flatfile_player_repository.py
bash tests/async/run_player_save_claim_mysql.sh
bash tests/async/with_disposable_mariadb.sh python3 tests/async/test_kept_character_journey.py --backend mariadb --server bin/server/dms_new
python3 tests/async/test_kept_character_journey.py --backend flatfile --server bin/issue-612-flatfile/server/dms_new
./scripts/format.sh --check
git diff --check
```

The MariaDB journey verifies owner, mapping and all three opening baselines **before** account login, so projection repair cannot mask a missing creation commit. The repository harness exercises rejected mapping insertion (all player/item/baseline writes roll back), same-attempt reconciliation, protection against replay over a later level, conflicting owner/PID and deletion tombstones. Codec tests round-trip the initial account and decode schema 14 plus all previously supported versions. Existing legacy-byte fixtures now omit schema-15 metadata, and the reset probe includes the production mapping-tombstone statement before checking reset postconditions. These are fixture compatibility updates, not changes to reset behavior.

Chunk-2 proof (all passed locally on 2026-11-03):

```sh
make -C src -j6
make -C src PERSISTENCE_BACKEND=flatfile BIN_ROOT=../bin/issue-612-flatfile -j6
python3 tests/async/test_flatfile_player_repository.py
python3 tests/async/test_flatfile_player_domain_repository.py
python3 tests/async/test_new_player_bank_hydration.py
python3 tests/async/test_flatfile_account_membership.py
python3 tests/async/test_flatfile_identity_repository.py
python3 tests/async/test_flatfile_character_delete.py
python3 tests/async/test_player_save_claim.py
python3 tests/async/test_kept_character_journey.py --backend flatfile --server bin/issue-612-flatfile/server/dms_new
./scripts/format.sh --check
git diff --check
```

The executable repository fixture rejects an unpublished first commit without any identity/domain/snapshot, recovers after the journal and each of five after-images, preserves all captured status fields and authoritative stats, retains membership count/time, and verifies replay, name competition, tombstones and monotonic PID allocation across recovery. Ordinary wallet, trade receipt and bank/deletion journeys remain green. Four harness manifests now link the account repository used to validate an initial owner.

Additional details for the next implementation session:

- Flat-file `sql_player_names_set/hold/release` are currently no-ops and name checks use the persistent catalog. The upcoming asynchronous saving state must retain an attempt-scoped reservation until the writer resolves, including after descriptor loss; repository competition guards alone do not prove the pending-name policy.
- A rollback of a retry transaction does not prove that an earlier ambiguous first commit never landed. Completion cleanup must reconcile the exact committed identity before releasing a reservation. Qualify an account being blocked after commit/before reconciliation too, and preserve a committed Keep while entry is denied.
- The current Keep UI still advertises Return before save acknowledgment, accepted-name/approval branches still need a common baseline, and account selection/override still need safe pre-entry routing. Chaos and ordinary kit resumption remain unimplemented acceptance gates; inventory emptiness is not a completion receipt. No recovery command or operations guide has been delivered yet.

Acknowledgment prerequisite proof (2026-11-03): both existing executable repository harnesses first failed when an account was blocked after the initial commit. After the fix, `bash tests/async/run_player_save_claim_mysql.sh` and `python3 tests/async/test_flatfile_player_repository.py` pass, including a separate fresh blocked-account attempt that publishes no identity/snapshot/membership. MariaDB also verifies the committed character's later level is not overwritten. Both `make -C src -j6` and `make -C src PERSISTENCE_BACKEND=flatfile BIN_ROOT=../bin/issue-612-flatfile -j6` pass. No schema change or new lifecycle field was needed. Logs: ignored `bin/tests/issue-612-blocked-{before,after}-{mariadb,flatfile}.log` and `issue-612-reconcile-*-build.log`.

Takeover proof (all passed locally on 2026-11-03; this chunk changes Python/docs only):

```sh
bash tests/async/with_disposable_mariadb.sh python3 tests/async/test_kept_character_journey.py --backend mariadb --server bin/server/dms_new --override telnet
bash tests/async/with_disposable_mariadb.sh python3 tests/async/test_kept_character_journey.py --backend mariadb --server bin/server/dms_new --override websocket
python3 tests/async/test_kept_character_journey.py --backend flatfile --server bin/issue-612-flatfile/server/dms_new --override telnet
python3 tests/async/test_kept_character_journey.py --backend flatfile --server bin/issue-612-flatfile/server/dms_new --override websocket
python3 -m py_compile tests/async/test_kept_character_journey.py
git diff --check
```

The flat-file leg builds the existing repository inspector under `bin/tests/` to read authoritative numeric stats; it does not infer them from screen text. The fixture explicitly observes the old socket closing. These controls cover ordinary approval-off/non-Chaos creation; pending approval, delayed initial completion and active Chaos grants still require the planned journeys.

Source-traced reuse points for the next acknowledgment chunk:

- `wait_for_writer()` / `writer_replied()` are already public in `account.h`; they match an asynchronous reply to a live descriptor by a unique request ID and tolerate descriptor loss. Reuse them rather than introducing another descriptor ID or retaining a raw descriptor in a queued job.
- `delete_character(ch, true, done)` already reports its durable outcome on the game thread and does not consume `ch` (`core/prototypes.h`, `core/files.c`). Staff decline can reuse this callback and the existing request ID instead of creating a second deletion implementation.
- Flat-file initial bank/item ownership hydration currently lives inside `writeCharacter()` after its terminal baseline acknowledgment. An asynchronous creation callback needs that same publication after commit; factor only that existing post-baseline step rather than queueing another initial snapshot or doing MariaDB I/O on the game loop.
- A narrow creation-completion hook in the existing player-save pipeline can notify the account continuation using immutable PID/revision/name/account/request context. No generic workflow/callback framework or second writer queue is required. Initial approval metadata, level-0 selection routing, staff acceptance/decline and save-failure cleanup must agree before the new saving-state chunk is considered qualified.

## Non-goals

No production queries, migrations, data repair, server restart, deployment, or bulk deletion in this implementation. Future production repair requires the user's permission and a per-record decision. No rested-bonus policy change, name-expiry service, PID reuse, blanket level-0 cleanup, global save-pipeline rewrite, new persistence backend, or changes to unrelated item-authority work.

#612 stays open until prevention, resumption, recovery capability, and the acceptance journeys below are implemented and proven. Historical #238/#489/#417 and merged item work are context, not additional issues to close.

## What current code establishes

Line references below refer to the inspected base. These are source findings, not new runtime reproductions of the incident.

1. **Allocation still happens at Keep.** [nanny.c](../../src/account/nanny.c#L4374) calls `init_char()` and `add_char_to_account()` after `select_keepchar()`. `init_char()` at 3900 allocates a monotonically assigned PID, hydrates initial revision/ownership state, and publishes the name reservation at 3912. Do not allocate another PID when resuming a kept character.

2. **The reported MariaDB ownership gap remains.** [account.c](../../src/account/account.c#L2609) builds an in-memory membership; its MariaDB comment at 2639 promises the first save will commit both player and mapping. [player_snapshot_capture.c](../../src/player/player_snapshot_capture.c#L106) captures status without account ownership. [player_snapshot_repository.c](../../src/player/player_snapshot_repository.c#L1035) inserts only PID/name, then commits components/opening baselines/revision in the existing transaction at 1192-1305. It never establishes the account mapping there. The comment describes a guarantee the implementation does not supply.

3. **Not all Keep branches save.** Ordinary approval-off Telnet queues `writeCharacter()` at [nanny.c:4434](../../src/account/nanny.c#L4434). Previously accepted names call the Chaos helper; that helper at 906 immediately returns outside Chaos. Approval waiting at 4414 saves no baseline. Therefore adding an owner to the ordinary snapshot alone does not cover accepted names or approval waiting.

4. **A queued save is not a committed save.** MariaDB [files.c:1329-1345](../../src/core/files.c#L1329) queues every ordinary `writeCharacter()`, including terminal-type calls. [player_save_pipeline.c:188-214](../../src/player/player_save_pipeline.c#L188) reports queue acceptance separately from writer completion. Its terminal wait at 465 observes written revisions, while [player_save_worker.c:169-187](../../src/player/player_save_worker.c#L169) retries connection/ambiguous outcomes in order. Reuse these distinctions; do not advertise a durable Keep because `writeCharacter()` returned true.

5. **Disconnect frees the body, not identity or queued work.** [comm.c:3726-3731](../../src/net/comm.c#L3726) cancels unsubmitted pre-entry kit work and calls `free_char()`. Session retirement at [player_save_pipeline.c:94-100](../../src/player/player_save_pipeline.c#L94) waits for outstanding saves. Kit cancellation at [item_movement_transaction.c:1573-1611](../../src/item/item_movement_transaction.c#L1573) retains active submissions and completion publication. Clearing the name immediately could let late work recreate the old character.

6. **Existing load repair cannot infer a missing owner.** [sql_player.c:1363-1444](../../src/sql/sql_player.c#L1363) repairs mappings from an active row whose saved owner matches the account, respecting deletion tombstones and financial baselines. [player_load_repository.c:261-316](../../src/player/player_load_repository.c#L261) requires a nonempty matching owner. Boot reloads reservations from `player_data` at [sql_player.c:710](../../src/sql/sql_player.c#L710). A NULL-owner row needs an explicit recovery decision.

7. **Account resumption needs changes beyond storage.** [account.c:1636-1650](../../src/account/account.c#L1636) sends a loaded character directly to `CON_PLAYING`/`enter_game()`, without the creation approval branch. `is_char_in_game()` at 2199 searches pre-entry descriptors too, closes the previous descriptor at 2247, then reuses the found body. The close path above frees non-playing bodies: durable membership will make this override path newly reachable more often. Preserve/refetch the body safely and route unfinished creation through approval/entry instead of treating it as an ordinary playing reconnect. This is a source-supported lifetime risk to reproduce in the focused harness.

8. **First entry and grants have different boundaries.** [nanny.c:1537](../../src/account/nanny.c#L1537) derives `new_character` from level 0; at 1931-1964 entry performs level-one initialization and starts ordinary equipment. Chaos equipment is submitted before entry at 875-919; account reload does not run that creation branch. Existing pending flags cover Chaos bank/epic rewards, but the transient creation-grant queue itself is not a durable per-character kit-completion record. Inventory emptiness alone cannot prove a full kit was delivered. Test and bind retries to the same grant operation rather than regenerating a new kit after interruption.

9. **Approval transitions must participate.** [actwiz.c:8013-8019](../../src/cmd/actwiz.c#L8013) records an accepted-name marker and goes through `CON_WELCOME`; that state saves and returns to the account menu at [nanny.c:4450](../../src/account/nanny.c#L4450). `do_decline()` at 7810 changes name/queue state without a durable creation cancellation. Once waiting characters are saved, approval and decline must update/release that same creation safely. Preserve staff approval requirements and accepted-name compatibility.

10. **WebSocket shares allocation, but not the interactive gap.** Current [ws_handlers.c:2390-2460](../../src/net/ws_handlers.c#L2390) allocates, adds membership, queues baseline/kit, commits admission, and enters in one handler. Admission failure still frees the pre-entry body. Current master also contains #625's race/class alignment and recent stale-item-load protections; retain them. Qualify rejection and delayed completion explicitly instead of claiming ordinary WebSocket disconnect reproduces the Telnet prompt gap.

11. **Flat-file failure differs.** [flatfile_account_adapter.c:227-279](../../src/flatfile/flatfile_account_adapter.c#L227) commits account scalars and membership together before the player snapshot. [flatfile_player_repository.c:612-640](../../src/flatfile/flatfile_player_repository.c#L612) needs that identity to establish initial domains; at 1004-1027 domains are established before the final snapshot transaction at 1222. [files.c:1361-1365](../../src/core/files.c#L1361) already waits for the first flat-file baseline. This avoids the identical MariaDB NULL-owner mechanism but leaves membership/domain-without-usable-snapshot boundaries to close.

The issue investigated `27f4c71c`; current relevant files have changed since then. This pass read the current functions and relevant diffs. It did not access production, rerun the issue's `/tmp` fixture, or treat the old executable reproduction as a fresh build of this base.

## Ablation decisions

- **Keep durable/resumable Keep.** The prompt explicitly offers to keep the rolled character, and the issue requests preservation/resumption. Deleting on disconnect would lose that outcome. No expiry timer or periodic reaper is needed.
- **Keep one creation commit through existing repositories.** MariaDB needs ownership/membership in its existing first-snapshot transaction. Flat-file needs its initial identity/domain/snapshot publication coordinated through the existing authority transaction. Separate queued SQL updates or account writes leave an intermediate orphan.
- **Keep a small pending-save transition and completion hook.** The real distinction is queue acceptance versus commit, including after descriptor loss. Reuse writer ordering, revision checks, load holds, and descriptor/runtime identity. Do not add a service, general workflow framework, second queue, or synchronous MariaDB query on the game loop.
- **Reuse level 0 for first-entry detection, existing accepted-name markers, and existing reward receipts.** Add only the durable approval-pending flag and grant-operation/completion information that cannot be reconstructed safely from these authorities. Do not create a parallel lifecycle database when existing saved flags/snapshot fields suffice.
- **Keep codec compatibility if snapshot metadata changes.** Flat-file snapshots are persisted through the codec (current schema version 14). Captured account context must survive worker ownership and retries; newly encoded lifecycle data must round-trip. Older supported snapshots must remain readable. This is required compatibility, not optional cleanup.
- **Keep targeted recovery and real socket/restart proof.** Existing source contracts do not cross this failure boundary, and a metadata-only fix cannot release existing unknown-owner rows safely.
- **Drop unrelated cleanup, broad fault infrastructure, global persistence format changes, and automatic orphan attachment/deletion.** Each retained change below closes a traced path or an explicit acceptance criterion. Extend existing fixtures before adding another test runner.

## Implementation sequence

### 1. Reproduce the exact boundary with maintained fixtures

Extend [test_creation_prompt_journey.py](../../tests/async/test_creation_prompt_journey.py) using its real Telnet client, choice helper, synthetic accounts, and isolated server lifecycle. Stop at Keep, save the ten selected stats, answer Y, disconnect at the final prompt, log into a fresh account session, select the kept character, and repeat after cold restart. Record the failing MariaDB case before implementation; use flat-file as a distinct baseline/control.

Use the disposable MariaDB runner and the database/environment setup pattern in [test_account_recovery_mysql_journey.py](../../tests/async/test_account_recovery_mysql_journey.py). The fixture must never inherit the checkout's operational database/listener. Supply valid minimal-world/frag-cap prerequisites as fixture data, with nonempty disposable credentials.

Add executable repository and completion-path cases to the existing save/account harnesses for initial owner/mapping, rollback, queue rejection, delay, ambiguous commit, and connection override. Source contracts remain secondary guardrails.

### 2. Establish a complete initial commit

Capture immutable account identity with the initial player snapshot before handing it to the writer; never consult a freed descriptor on a worker. Keep ordinary saves from changing an established owner based on stale account context.

For MariaDB, extend the existing first-save transaction to validate the attempt's PID/name/account, insert the owned active player, save the full usable level-0 snapshot, establish opening baselines, and create the account-character mapping together. A retry of the same attempt must recognize its committed result. Reject conflicting owner/PID/name and deletion tombstones; do not use an upsert that steals or reactivates someone else's character. Preserve account creation counters, projection fields, and existing rename/transfer semantics.

For flat-file, stop publishing a new membership through the ordinary account-save path before a usable snapshot exists. Prepare the initial membership, required account/domain after-images, and snapshot through the existing authority transaction/recovery mechanism. Refactor only the initial-player domain preparation needed to avoid its current identity-before-domain-before-snapshot dependency. Preserve monotonic PID allocation separately: consuming a PID without committing a character is valid. Respect current lock ordering; fault-test each publication/recovery boundary.

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

Preserve level-zero-to-one initialization and all ten chosen stats. For first-entry kits, reuse existing critical-command receipts and reconciliation, with a durable per-PID binding to the kit operation/completion state so retries resume the same grant. Persist the binding before submission; publish/record completion with the existing transaction facilities. If no suitable existing field stores that binding, add only the narrow metadata this path needs, with both-backend compatibility. Do not infer completion merely from a nonempty bag, generate new item UIDs for an already submitted kit, or clear the pending intent before durable completion. Keep existing bank/epic/achievement intents and command blocking. Prove interruption after level-one baseline but before kit completion, as well as active pre-entry kit completion after disconnect.

### 5. Provide guarded recovery for existing broken records

Add a narrowly privileged staff recovery entry point alongside existing character administration, with inspect, explicit attach, and explicit release operations. Reuse `delete_character()`/backend deletion and projection repair; if they require a loadable body, factor only the validated PID/name deletion work needed for an otherwise unloadable orphan. Do not create a second destructive SQL/file-deletion implementation.

Inspection is read-only and identifies PID/name, owner, active/tombstone status, mappings, usable snapshot/domain state, and outstanding save/grant work. Mutation names an exact PID and expected name and revalidates under the backend's transaction/lock/fence. Reject live/pending actors, conflicting owners, renamed/replaced identities, established/approved legitimate characters, and unproven safety conditions.

- **Usable snapshot, demonstrable owner, missing mapping:** repair owner/membership atomically, preserving stats, balances, rewards, approval, and PID; then load through the account normally.
- **NULL/empty owner, usable snapshot:** require staff to supply a verified account with external incident/ownership evidence before attach. Never auto-guess. If evidence cannot establish ownership, leave unchanged or perform a separately authorized explicit release.
- **Membership without a usable snapshot:** distinguish genuine absence from I/O/corruption/pending write. Restore only from an existing verified recovery after-image; never manufacture lost stats. Otherwise report that restoration is impossible and require explicit release of the exact broken attempt.
- **Release:** settle/fence already submitted work first, use existing deletion/tombstone semantics, then forget the live name index only after durable success. Prove a delayed save or grant cannot resurrect the released PID or affect a new claimant of the name.

Add `docs/operations/kept-character-recovery.md` with the exact inspected fields, staff commands, ownership-evidence requirement, dry inspection examples using synthetic data, retry/refusal behavior, and postconditions. That file is an implementation deliverable. No production player/account identifiers belong in commits. The issue's additional ownerless row remains an unverified candidate until its current state is inspected with permission.

### 6. Complete acceptance across the real paths

For each backend, run the basic post-Keep/pre-entry disconnect/resume/restart journey for all eight combinations of ordinary/already-accepted name, approval off/on, and Chaos off/on. Where an accepted marker exempts approval, assert the exemption explicitly. Use synthetic names/accounts/accepted markers and restore fixture state between cases.

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
- `src/flatfile/flatfile_account_adapter.c`, `flatfile_identity_repository.c/.h`, `flatfile_player_repository.c`, `flatfile_player_domain_repository.c/.h`: initial atomic publication using current authority operations.
- `src/player/player_snapshot_repository.c`, `src/sql/sql_player.c`, `src/core/files.c`: initial SQL ownership/membership, safe recovery, existing deletion reuse.
- `src/cmd/actwiz.c` and existing command/prototype registration files: staff approval/decline and scoped recovery dispatch. `src/core/structs.h`/`defines.h` only for necessary pending-state/flag fields.
- `src/item/item_movement_transaction.c` and existing grant/receipt types only where durable kit resumption requires them; retain the existing coordinator.
- Existing creation/stat-choice/save/identity/deletion/flat-file harnesses; one focused `tests/async/test_kept_character_journey.py` may share both backends and protocols rather than duplicating infrastructure.
- `docs/operations/kept-character-recovery.md`, affected creation/recovery help, and this plan's completion evidence.

A guarded additive migration is conditional on a demonstrated need for durable kit-operation/approval metadata that existing saved fields cannot carry; ownership/membership columns already exist. Decide that from the step-4 receipt trace before adding schema, and implement the equivalent flat-file representation. No new dependency or background daemon is planned.

## Proof commands and completion gates

Run the narrow repository/runtime tests changed in each step first. Existing relevant commands include:

```sh
python3 tests/async/test_player_snapshot_capture.py
python3 tests/async/test_player_item_snapshot_codec.py
python3 tests/async/test_player_save_pipeline.py
python3 tests/async/test_player_save_worker.py
python3 tests/async/test_player_save_claim.py
python3 tests/async/test_flatfile_account_membership.py
python3 tests/async/test_flatfile_player_repository.py
python3 tests/async/test_account_character_delete_runtime.py
python3 tests/async/test_creation_grant_reconciliation.py
python3 tests/async/test_creation_grant_batch_submission.py
python3 tests/async/test_creation_prompt_journey.py
python3 tests/async/test_character_stat_choice_journey.py
bash tests/async/run_account_character_identity_mysql.sh
bash tests/async/run_account_character_projection_mysql.sh
bash tests/async/run_player_save_claim_mysql.sh
```

Use each database wrapper's documented disposable setup. For the planned shared journey, expose `--backend` and `--server` arguments only if needed by the existing fixture conventions, then record its exact final invocation here. Its MariaDB leg must run through `tests/async/with_disposable_mariadb.sh`. Reuse existing authority fault-test hooks for flat-file and writer locks/fault seams for MariaDB; add only a local test seam if a required failure cannot otherwise be triggered.

After C/C++ changes, run `./scripts/format.sh --check` and `make -C src`. Build the flat-file backend separately under `bin/`, for example `make -C src PERSISTENCE_BACKEND=flatfile BIN_ROOT=../bin/issue-612-flatfile`; verify the selected binary/backend in each journey. All generated artifacts stay under `bin/`.

Completion requires every acceptance scenario above, clean changed-line formatting/builds for both backends, an inspected narrow diff, and recorded exact commands/results. Do not wait for CI. Report any missing runtime evidence explicitly and leave #612 open if a required gate is unverified.

## Planning verification and implementation estimate

This planning pass read current source/callers/tests and relevant diffs from the issue's base, verified the GitHub Development branch link and inspected the staged additions. Local-link existence checks and byte-for-byte preservation of the prior #584 plan passed; `git diff --cached --check` passed. No C/C++ changed, so no build, database test, or gameplay qualification was run or claimed for this documentation-only commit.

Estimate for me to implement and locally validate the complete scope: **12-18 active hours**, including approximately 4-6 hours for both initial commit paths/codec/completion handling, 3-4 hours for resume/approval/grants, 1-2 hours for guarded recovery, and 4-6 hours for regression journeys, fault/restart qualification, and final review. This is agent execution time, not a human-team estimate. It includes the acceptance coverage above; production deployment/repair and time waiting for external ownership evidence are excluded. The main uncertainty is the required durable kit-operation binding and flat-file initial transaction/lock refactor; revise the estimate if those traces reveal additional compatibility work.
