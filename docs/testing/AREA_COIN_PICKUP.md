# Area-authored coin pickup regression

Issue #213 affects `ITEM_MONEY` prototypes other than the generic `VOBJ_COINS`
prototype. The reported example is `areas/obj/library.obj` #402013: ten platinum
hidden inside statue #402001 by a `P` zone reset.

The pickup command accepted money by type, but its transaction payload substituted
vnum 3 while capturing the object's actual vnum in the snapshot. The coin command
then required both records to use vnum 3. Repository validation and player reload
also assumed that all physical money used this one prototype.

On the current base, a second problem prevents the first pickup after admission:
the admission callback runs while its completed movement remains in the pending
map. The callback's pickup continuation consequently sees its own actor as busy.
Ordinary admission now releases that completed movement before calling the
continuation, following the existing movement-completion convention. Creation
grants still retain pending work until publication succeeds.

## Behavior

Coins now move in memory (Phase 2 of the
[persistence reset](../adr/0002-persistence-reset-memory-is-the-authority.md)):

- Get, take and put handle any `ITEM_MONEY` object by type, whatever its vnum, and
  add a picked-up pile to the wallet at once. The player's save writes the wallet.
- A pile a player keeps in a container is an ordinary item: the save writes it with
  its amount and claims it, and a load reads that amount back. An older server kept a
  pile's amount in its custody row (`coin_payload`); that value is no longer read, so
  a pile changed in memory cannot come back at its old amount. A pile such a server's
  coin transaction spent stays spent.

The vnum-3 requirement for the pile created from a player's death wallet is
unchanged: that check validates a specific generated object, not ordinary loot.

## Regression checks

`python3 tests/async/test_area_coin_pickup.py` boots isolated flat-file servers
and copies the actual statue and hidden-money prototypes into the minimal world,
changing only their vnums. An `O` reset places the statue and a `P` reset puts the
coins inside it. Each fresh character searches the statue and picks up its coins
using one of `get coins statue`, `get all.coins statue`, and `take all statue`,
then saves. The test checks a durable ten-platinum wallet, an empty statue, and no
additional credit on a repeated pickup. `--server /absolute/path/to/dms_new` can
reuse an already built flat-file binary. All account, world, and authority data
are synthetic and temporary; the checkout's `.env` is not read.

Additional focused checks:

```sh
python3 tests/async/test_take_coins.py
python3 tests/async/test_currency_in_memory.py
python3 tests/async/test_flatfile_item_repository.py
bash tests/async/run_experience_trophy_mysql.sh
python3 tests/async/test_live_item_movement_contract.py
```

The player-load harness in `run_experience_trophy_mysql.sh` loads a pile whose custody
row still holds an older amount and checks that the saved amount wins.
