#!/usr/bin/env python3
"""The MariaDB alliance save replaces the list in one writer job (persistence reset
phase 2, step 8): the DELETE and every INSERT, with its tribute, go to
sql_queue_statements(), and nothing runs on the game thread's connection."""
from _paths import SRC
import sys

text = (SRC / "alliances.c").read_text()

start = text.find('void save_alliances()')
mariadb = text.find('#else', start)
end = text.find('#endif', mariadb)
body = text[mariadb:end] if -1 not in (start, mariadb, end) else ''

delete_stmt = body.find('"DELETE FROM alliances"')
insert_stmt = body.find(
    "INSERT INTO alliances (forging_assoc_id, joining_assoc_id, tribute_owed) VALUES ('%d', '%d', '%d')")
tribute_argument = body.find('alliance.tribute_owed', insert_stmt)
queued = body.find('sql_queue_statements(statements)', tribute_argument)
loader_select = text.find(
    'SELECT forging_assoc_id, joining_assoc_id, tribute_owed FROM alliances')
loader_assignment = text.find('alliance.tribute_owed = atoi(row[2]);')

ok = True
if not body:
    print('missing the MariaDB save_alliances branch')
    ok = False
elif not (-1 < delete_stmt < insert_stmt < tribute_argument < queued):
    print('the alliance save does not queue DELETE then INSERTs with tribute_owed')
    ok = False
for call in ('qry(', 'sql_begin_transaction', 'sql_commit', 'sql_rollback'):
    if call in body:
        print(f'save_alliances still calls {call} on the game thread')
        ok = False
if loader_select == -1 or loader_assignment == -1:
    print('MySQL alliance loader no longer exposes tribute_owed')
    ok = False

sys.exit(0 if ok else 1)
