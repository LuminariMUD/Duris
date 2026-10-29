# Issue #444: preserve denominations in physical coin transfers

Status: **planned; implementation not started**. Updated 2026-10-30.
Issue: [Duris #444](https://github.com/LuminariMUD/Duris/issues/444).
Branch: [`branch/issue-444-coin-denominations`](https://github.com/LuminariMUD/Duris/tree/branch/issue-444-coin-denominations).
Source baseline: `origin/master` at `b23ea8c65a467d17683ccd5de91f66b362209d06`.
Worktree: `/home/aiwithapex/projects/duris-worktrees/issue-444-coin-denominations`.

This plan follows the repository's [ablation skill](../../.agents/skills/ablation/SKILL.md).
The previous shared plan, including its #428/#445 qualification and review record,
is preserved byte-for-byte as [plan-issue-428.md](plan-issue-428.md).
The authorized deliverable for this branch checkpoint is this committed/pushed
plan and issue association; the implementation steps below remain future work.

## Outcome

Physical coins retain their copper, silver, gold and platinum counts through
pickup, explicit give, put, drop and rejected-transfer refunds. A player with
40 gold can retrieve those coins from a bag and give 10 gold four times without
an intervening exchange. Each successful transfer removes exactly the selected
coins, leaves unrelated denominations unchanged and delivers exactly those
coins to the recipient or pile. Failed transfers leave the source intact or
restore the exact debited vector, with no duplicate credit or success message.

Preserve the existing command restrictions, NPC behavior except denomination
conversion, staff minting exception, overflow refusals, wallet revision/dirty
state, client feedback and save ordering. Rewards carrying an explicit coin
vector use the same semantics; value-only rewards retain their existing meaning.
Saved wallets and persistent containers must retain their exact counts after
relog and server restart.

## Source findings and limits

These findings were checked in the worktree above, rather than accepted from
issue #444's older `8e95eb5dd` source links. Line numbers refer to this baseline.

- `src/cmd/actobj.c:310-366`: `credit_coins()` accepts a copper-equivalent value;
  PCs use `currency_transaction_submit_wallet_value()` and NPC/no-PID fallbacks
  use `ADD_MONEY()`. `take_coins()` has the exact selected four-element `got`
  array but reduces it to value before credit. Its source-pile subtraction,
  relabelling, messages and corpse write happen only after credit succeeds.
- `src/cmd/actobj.c:569-605`: ordinary `get()` has a second money route which
  also discards the vector. Both routes must change; fixing `take_coins()` alone
  misses direct pickup. Keep its 64-bit total for logging, not as wallet input.
- `src/cmd/actobj.c:2600-2972`: `coin_debit_context.amount` already holds the
  exact vector, and put/drop already publish that vector. The loss happens in
  `submit_coin_debit()` through `SUB_MONEY()`, in `begin_coin_give_credit()`
  through value credit, and in `refund_committed_coin_debit()` through value
  refund. No new transfer context or durable transaction system is needed.
- `src/economy/currency_value.h:7-45` and `src/core/utility.c:2247-2300,2363-2379`:
  positive value credit canonicalizes only the incoming amount. Thus 35 existing
  gold plus 5 gold worth stays 40 gold, while 40 gold worth credited to an empty
  purse becomes 4 platinum. Negative PC value spending canonicalizes the entire
  remainder: 40 gold minus 10 gold worth becomes 3 platinum. These are source
  conclusions; the historical executable probe in the issue was not rerun here.
- `src/economy/currency_transaction.c:140-233` and its header: vector submission
  already validates every resulting denomination before mutation, advances the
  wallet revision, marks status dirty and updates GMCP. Completion is synchronous.
  **Submission returning true does not prove commitment:** insufficient balance,
  overflow or a reserved trade can call completion with `committed=false` and
  still return true. Pickup's revision check is intentional. The current debit
  wrapper calls publication manually after `SUB_MONEY()` returns success; replace
  that assumption with the actual transaction completion when switching to vectors.
- `src/cmd/actoth.c:2530-2624`: deposits and withdrawals already use exact wallet
  and bank vectors. Reuse that API; no bank implementation change is indicated.
- `src/cmd/actobj.c:2744-2752,2778-2782,2812-2820`: PC give saves the sender before
  recipient credit; storage/corpse put saves the sender before destination save.
  Keep these boundaries. The currency header explicitly describes a save-order
  model that favors avoiding duplication over crash-atomic transfers; do not
  promise stronger durability than this patch provides.
- `src/cmd/actobj.c:4088-4144`: ordinary `give` checks the selected denomination,
  while `MAXLVL` PCs intentionally skip debit. Preserve both. NPCs and no-PID
  actors cannot simply be passed to the PC transaction API, which rejects them.
- `src/world/quest.c:120-171,260-278,728-813`: the legacy quester calls `do_give()`
  before checking completion. Coin goals compare `GET_MONEY(mob)` and consume
  value; coin rewards use value-only `ADD_MONEY()`. A quest saying "gold" does
  not establish a denomination-specific reward or completion rule.
- `src/world/world_quest.c:253-262,370` also pays mercenaries by value. The zone
  story production/runtime files catalogue and track legacy completions; they
  are not evidence of a separate gold-paying reward implementation. Legacy item
  rewards use object creation/grant, preserving authored money-object fields
  until the pickup boundary. Do not convert every quest reward into gold.
- Other inspected value callers include shop settlement in
  `src/economy/shop.c:2664-2684`, world-quest fee refunds in
  `src/specs/specs.mobile.c:10876-10882`, and denomination-labelled wagers in
  `src/economy/cardgames.c:581-583` / `src/specs/specs.gellz.c:391,768`.
  They do not go through the physical give/put/drop adapter. This inspection
  supports keeping the global value API unchanged; it does not qualify those
  separate gameplay systems or expand #444 into an economy-wide rewrite.
- `src/player/player_snapshot_capture.c:174-177`,
  `src/player/player_load_materialize.c:594-597`, and
  `src/flatfile/flatfile_player_repository.c:629-634` already save/load four
  separate counts. There is no evidence that a schema or data migration is needed.
- `tests/async/test_take_coins.py` replaces production `credit_coins()` with a
  one-integer purse. `test_coin_command_transaction_contract.py` explicitly
  expects the value-based calls. Their current green results cannot establish
  denomination preservation. `test_currency_in_memory.py` already links real
  production transactions and covers synchronous refusal, revisions and trade
  reservations; reuse its setup and service stubs.

Emp's exact NPC/quest and live build remain unidentified in the issue and its
empty comment thread. Do not choose a quest from similar wording or claim to
have reproduced that player's route. Before changing a particular value-only
reward, identify its NPC/VNUM, definition and intended currency from the report
or owner, then trace its actual handler. This uncertainty does not prevent the
shared transfer fix or a synthetic quest journey; it remains explicit in the
implementation handoff and prevents claiming that specific reward verified.

## Non-goals and ablation decisions

- Keep `ADD_MONEY()`, `SUB_MONEY()` and `currency_wallet_value_delta()` value
  semantics for prices, fees, change, value-only rewards and unrelated callers.
  Do not auto-exchange a wallet to satisfy `give N gold`; preserve the requested
  physical coins instead.
- Keep the existing transaction facade, publication helpers and four-element
  contexts. Drop a new currency abstraction, setting, async queue, ledger,
  two-party transaction coordinator or generic test framework: none is required
  to stop the traced conversions.
- Keep checked NPC/no-PID fallbacks because the PC facade does not accept them.
  Keep all-components-before-mutation validation, rather than partially applying
  a vector. Keep persistent PC writes centralized in the transaction facade.
- Keep every refund boundary and real command/persistence proof. A helper-only
  test or conserving total value would miss the reported failure.
- No repair of historical purses, guessed reward-denomination migration, generated
  area edits, production deployment, player-data editing or full burn-in.
  Existing converted coins can still be exchanged through the bank.

## Files

Expected production changes are confined to `src/cmd/actobj.c`: reuse
`credit_coins()`, `submit_coin_debit()`, existing give completion/context and
refund/publication functions. Keep any necessary checked NPC mutation local
and guarded from persistent PCs; update source contracts narrowly to enforce
that boundary rather than adding a broad exemption for all wallet writes.

Extend `tests/async/test_take_coins.py`,
`tests/async/test_coin_command_transaction_contract.py` and, where its existing
fixtures help, `tests/async/test_currency_in_memory.py` and
`tests/async/test_currency_transaction_contract.py`. Add a focused native
coin-transfer test only if executing debit/give/refund paths would tangle the
existing pickup harness. Extract production functions and link the real
currency implementation; stub external services, never the arithmetic under test.

Add one focused `tests/async/test_coin_denomination_journey.py`, reusing the
minimal world, client, flat-file build and snapshot inspector from
`test_flatfile_combat_journey.py`, and the currency/bag patterns from
`test_flatfile_first_session_currency.py` and
`test_flatfile_auction_coin_put_journey.py`. Do not build a second socket framework.
Update this plan with implementation evidence. Edit a specific quest/content
file only if the reward investigation identifies an explicit denomination that
still bypasses these fixed routes, and name that file before making the change.

## Implementation sequence

1. **Expose the conversions with production code.** Replace the pickup test's
   scalar credit stub with real per-denomination wallet behavior and production
   credit/transaction functions. Add the debit, recipient and refund assertions
   below. Show denomination assertions failing on the unmodified baseline, while
   current ordering/refusal controls remain meaningful. Preserve existing pickup
   text, partial-pile and corpse tests.
2. **Carry vectors through pickup and debit.** Pass the selected counts from
   both pickup routes to the existing credit adapter and then the PC vector API.
   For explicit debits, negate the requested vector and use the real completion
   callback to publish exactly once after commitment; do not manually publish
   on submit=true. NPC/no-PID paths validate all resulting counts, subtract/add
   exactly those coins and preserve applicable dirty/GMCP behavior. All balances
   stay within `0..INT_MAX`; keep arithmetic in 64 bits. Remove value conversions
   and aggregate-int restrictions made obsolete by vector movement, while
   retaining parser limits, per-denomination limits and value-based log thresholds.
3. **Preserve give and compensation.** Credit PC and NPC recipients with the
   requested vector. Keep sender-first saving and the existing MAXLVL no-debit
   route. Return the same vector on destination loss, recipient refusal, failed
   object creation or failed container publication. Existing give context already
   records amount and coin type, sufficient to reconstruct its single-type
   refund; do not add redundant state. Refund success must observe commitment,
   not just submission, and refusal must remain visible through the existing
   diagnostic path. No canonical-value or auction-value fallback may silently
   replace an exact refund. Since completion is synchronous, eliminate any
   obsolete in-flight rationale in comments touched by the change.
4. **Cover rewards and actual gameplay.** A money-object reward and an explicit
   denomination give must use the corrected paths. Exercise a synthetic legacy
   quest through its actual `quester` handler so all four payments reach quest
   completion, rather than merely checking an NPC's wallet. Trace Emp's actual
   quest when identifiable; retain value-only payouts unless its definition and
   intended behavior justify a specific content change. Record unresolved identity
   honestly rather than silently declaring this acceptance item complete.
5. **Qualify and review.** Run the focused native checks, isolated journey,
   required build/format checks and documentation checks. Review the final diff
   against every outcome and remove unnecessary adapters or state. Record exact
   commands, backend coverage and any unavailable checks before implementation
   commit/push/review. External CI is not a completion gate.

## Proof and acceptance

The regression assertions must compare `[copper, silver, gold, platinum]` counts,
revision changes, source/destination ownership and feedback, not only total value.

- Pickup: empty purse plus 40 gold becomes `[0,0,40,0]`; 35 gold plus 5 gold
  remains 40 gold; `[3,12,17,0]` is not normalized. Cover full and selected partial
  pickups from floor, bag and PC corpse, including direct `get()` and selected
  `take_coins()` routes. Assert the exact residual pile, extraction/relabel behavior
  and existing messages. Refused credit leaves every pile field and revision alone.
- Debit: give, put, drop and `drop all.coins` preserve unselected counts. Four
  successful 10-gold debits from 40 leave 30, 20, 10 and 0 gold. Include mixed
  wallets and a valid vector whose copper-equivalent total exceeds `INT_MAX`,
  so no obsolete value cast can truncate or reject an otherwise valid transfer.
- Recipients: PC-to-PC, PC-to-NPC and NPC-to-PC give preserve the exact type;
  include NPC pickup/debit and existing no-PID fallback behavior. Staff credit
  still mints the requested type without debiting or refunding the staff purse.
- Failure: source short of the selected type cannot spend other denominations;
  PC/NPC recipient overflow, invalid PC identity, destination disappearance,
  closed/unavailable container, existing-pile overflow and allocation/publication
  failure change nothing or restore the original vector exactly once. Verify
  submit=false and submit=true/committed=false separately, including the current
  reserved-trade refusal. No successful give/put/drop announcement on refusal.
- Revision/order: successful PC mutations advance revisions and dirty status;
  rejected ones do not. Assert sender save precedes PC recipient credit and
  storage/corpse save, and preserve the existing bank ordering. A refund after
  sender-save must restore live state and remain dirty for the subsequent save.
- Rewards: an authored gold money pile retains gold after grant/pickup, and an
  explicit NPC gold give retains gold. Value-only reward controls still use
  canonical incoming change and leave pre-existing denominations alone. Do not
  alter legacy quest value goals or infer coin types from descriptive text.
- Real journey: create disposable local characters below MAXLVL, seed the bank
  with a known gold balance, withdraw 40 gold, put/get it through a bag, and make
  four `give 10 gold` payments through a synthetic quest NPC. Assert each purse
  and completion. Relog and restart at intermediate nonzero-wallet and bag-held
  checkpoints, then continue payments; also verify persistent recipient credits
  and refused transfers do not duplicate coins after saving/reload. Use durable
  snapshot inspection as well as command output. Floor coins and NPC wallets
  need only the persistence guarantees they already have.

Planned commands (the new journey is created during implementation):

```sh
python3 tests/async/test_take_coins.py
python3 tests/async/test_coin_command_transaction_contract.py
python3 tests/async/test_currency_in_memory.py
python3 tests/async/test_currency_transaction_contract.py
python3 tests/async/test_money_carry_count.py
python3 tests/async/test_coin_denomination_journey.py
python3 tests/async/test_flatfile_auction_coin_put_journey.py
python3 tests/async/test_area_coin_pickup.py
make -C src
./scripts/format.sh --check
python3 tests/async/test_documentation_contract.py
git diff --check
```

Run any additional native test introduced for the missing transfer paths. Reuse
one built flat-file server across compatible journeys. The focused restart
journey qualifies flat-file persistence; a MariaDB build or stubbed save-order
test alone must not be reported as a MariaDB runtime qualification. Exercise
the same commands on an isolated MariaDB fixture if available and report its
coverage separately. Use local/test settings, loopback listeners and disposable
accounts/state; keep new compiled outputs under `bin/`. No production operations
are needed for the plan or core implementation.

## Estimate and planning checkpoint

Estimated **3-5 hours of my active implementation time** for the shared repair,
native regressions, isolated quest/relog/restart journey, build and reviewable
commit. Rough allocation: 30-45 minutes for failing regressions, 45-75 minutes
for the transfer/refund changes, 60-100 minutes for command/persistence proof,
and 30-60 minutes for build, documentation and final review. Reuse of existing
fixtures is assumed. Allow an additional 1-2 hours if Emp's identified quest
needs a separate explicit-denomination reward fix or local DB setup is required;
waiting for its identity, external review, merge and deployment are excluded.

Planning validation on 2026-10-30 at the baseline above:

- `python3 tests/async/test_take_coins.py`: passed; its scalar purse limitation
  remains and is explicitly addressed above.
- `python3 tests/async/test_coin_command_transaction_contract.py`: passed;
  current assertions still encode the value-based implementation.
- `python3 tests/async/test_currency_in_memory.py`: passed under ASan/UBSan,
  including range refusal, revisions, save order and trade reservations.
- `python3 tests/async/test_currency_transaction_contract.py`: all 9 tests passed.
- `python3 tests/async/test_documentation_contract.py`: all 14 tests passed.
- `git diff --check` passed. The preserved #428 plan and the original HEAD copy
  have the same SHA-256: `db2e06ff1afe39dba4629cc840c579b994e04965df0e31995174625eee95fdbf`.

Only planning documents change at this checkpoint. No full server build,
new denomination regression, gameplay journey, reward fix or production/live
verification is claimed. The implementation acceptance items above remain open.
Issue #444 is the identified work item; a targeted open GitLab mirror search
for coin issues returned unrelated collector/flight work, not a matching item.
GitHub's native Development association links #444 to this branch, verified
with `gh issue develop 444 --repo LuminariMUD/Duris --list`. Retain the issue
until implementation and its acceptance work are complete; this plan does not
close it.
