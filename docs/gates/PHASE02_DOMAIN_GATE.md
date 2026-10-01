# Phase 02 Transactional Domain Gate

Phase 02 gameplay mutations use bounded, schema-versioned critical commands. The
coordinator assigns or preserves a 128-bit operation ID, journals before worker
eligibility, fences every declared entity key, and publishes an exact completion only
after the repository resolves the commit. The database transaction owns inbox dedupe,
current state, immutable ledgers/outcomes, and any durable outbox record.

## Active durable routes

| Domain | Current state / outcome | Ordering keys | Publication |
|---|---|---|---|
| Epic | `player_data`, `epic_ledger` | player | exact completion + outbox |
| Wallet/bank | player/account bank, `currency_ledger` | player + account | exact completion + outbox |
| Item custody | `item_current_owner`, ownership ledger | item + owners | exact completion + outbox |
| Auction | auction/custody/ledger rows | auction + item + players/accounts | exact completion + outbox |
| PvP/combat | frag/epic/currency outcome ledgers | all participant players | exact completion + outbox |
| Artifact/guild | domain state and outcome ledgers | actor + artifacts + guild | exact completion + outbox |
| Boon/reward | progress/shop and bounded outcomes | player | exact completion + outbox |
| Zone touch | zone/history/alignment/participants | zone + participants | exact completion + outbox |
| Session audit | `session_audit_outcome` | player | committed inbox result |

The Phase 01 player/world snapshot journals remain typed recovery routes. The legacy
item/scalar/large queues, their flat fallback log and the raw SQL executor are gone.

## Reconciliation and recovery

On an explicitly local/development/test database, run:

```bash
migrations/reconcile_phase02_domains.sh
```

Any nonzero mismatch is a release blocker. Do not repair with direct SQL. Preserve the
inbox, journal, ledger, and current-row evidence, determine the owning domain, and issue
only a guarded idempotent command or reviewed additive repair migration. Ambiguous
commits are resolved by operation-ID inbox lookup; outbox delivery is retried by its
destination identity.

Queue overload, journal failure, unavailable workers, or fences reject/defer admission
before gameplay success. Copyover and shutdown quiesce admission, drain exact
completions/outbox publication, and retain typed journal records that were not durably
acknowledged.
