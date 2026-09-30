#!/usr/bin/env python3
"""shutdown_ships() saves every player ship through write_ship() and opens no
transaction on the game thread's connection (persistence reset phase 2, step 8):
on MariaDB each save is a writer job, in order behind the saves the shutdown
flush queued just before it, so an older queued save can never land after a
newer direct one. A ship that cannot be saved still escalates."""
from _paths import extract_function
import sys

body = extract_function('ship_base.c', 'void shutdown_ships()')

ok = True
for call in ('sql_begin_transaction', 'sql_commit', 'sql_rollback', 'mysql_real_query'):
    if call in body:
        print(f'shutdown_ships still calls {call}')
        ok = False
guard = body.find('if (!write_ship(ship) && !IS_NPC_SHIP(ship) && SHIP_LOADED(ship))')
if guard == -1 or body.find('panic_corruption("shutdown_ships", "write_ship failed")', guard) == -1:
    print('ship shutdown write failure escalation missing')
    ok = False

sys.exit(0 if ok else 1)
