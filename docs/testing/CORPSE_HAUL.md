# Corpse bulk-loot journeys (#256, #378)

`get all corpse` captures the corpse's display name for that operation. When
the first item is taken, the looter and source-room observers see the start.
The haul lists only delivered items and the coin amounts actually taken. At the
end the player sees the sorting line, the haul, and then partial/failure
notices. Both NPC and player corpses use this presentation; the player-corpse
persistence flag keeps its existing meaning.

The haul runs at once, in memory: it selects the items, applying the carry
count and weight limits as it goes, then takes each one. Each selected coin pile
gives up only the denominations it held when it was selected. An item that an
earlier pickup moved or destroyed is reported as no longer available rather
than acquired. The next save of the player and of the corpse records where the
items went.

## Local validation

```sh
python3 tests/async/test_corpse_haul.py
python3 tests/async/test_bulk_get_publication.py
python3 tests/async/test_money_carry_count.py
python3 tests/async/test_take_coins.py
```

`test_corpse_haul.py` executes the production selection, pickup and reporting
functions under ASan/UBSan: NPC/player presentation, coin-only and mixed loot,
scrap, a later pile with nothing to take, the count cap, a malformed sibling
cycle, failed live delivery and strict NPC publication.

The actual three-player MariaDB journey also passed:

```sh
TEST_DB_HOST=127.0.0.1 TEST_DB_USER=... TEST_DB_PASSWORD=... \
  python3 tests/async/run_corpse_haul_journey.py /absolute/path/to/mariadb/server
```

Use a disposable loopback database. The runner creates and drops a unique
schema; it never reads checkout credentials. It creates three real accounts and
characters. The looter kills Raoul through actual combat; a second player stays
at the corpse and a third waits in the next room. Coins and items move in memory,
so the haul of Raoul's coins and banana completes at once: the second player sees
it start and the third sees nothing. After an actual player death, it repeats the
mixed equipment-and-coin movement against the player's corpse. Each stage asserts
the haul, observer output, and the saved custody and wallet. A live reconnect
retains the acquired inventory without replaying a completed haul, and saves
succeed.

Early integration attempts exposed fixture expectations rather than runtime
failures: `Raoul` is capitalized, a linkdead reconnect skips the ordinary
`Play as` confirmation, and a player's corpse has a character-name short
description even when its room description names the race. Those expectations
were corrected before the complete journey passed. This is local validation;
GitHub CI is not used as the acceptance gate.
