#!/usr/bin/env python3
"""The MariaDB cargo market save is one writer job (persistence reset phase 2, step
8): both deletes and the four inserts go to sql_queue_statements(), in one
transaction, and the staff reload reads on the writer. Nothing runs on the game
thread's connection after boot."""
from _paths import SRC
from contract_text import squeeze
import sys

text = (SRC / "ships/ship_cargo.c").read_text()
start = text.find('int write_cargo()')
mariadb = text.find('#else', start)
end = text.find('#endif', mariadb)
body = text[mariadb:end]

ok = True
queued = squeeze(body).find(squeeze('sql_queue_statements({ "delete from ship_cargo_market_mods", '
                                    '"delete from ship_cargo_prices",'))
if start == -1 or queued == -1:
    print('write_cargo does not queue the market replacement as one job')
    ok = False
for call in ('qry(', 'sql_begin_transaction', 'sql_commit', 'sql_rollback'):
    if call in body:
        print(f'write_cargo still calls {call} on the game thread')
        ok = False

command = text[text.find('void do_world_cargo('):]
reload = command[command.find('is_abbrev(arg, "reload")'):command.find('is_abbrev(arg, "reset")')]
if 'sql_read_for(ch, CARGO_MODS_QUERY' not in reload:
    print('the cargo reload does not read on the writer')
    ok = False

sys.exit(0 if ok else 1)
