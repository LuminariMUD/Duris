#!/usr/bin/env python3
"""Guildhalls never query on the game loop (persistence reset phase 2, step 8).

On MariaDB a hall's and a room's save and delete are queued on the persistence
writer, new ids come from memory (the boot load reads the highest stored ones),
and a reload rebuilds the rooms from memory instead of reading them back.
"""
from _paths import extract_function
import sys

failures = []


def mariadb_branch(body):
    return body[body.index('#else'):body.index('#endif')] if '#else' in body else body


for signature in ('bool save_guildhall(', 'bool save_guildhall_room(',
                  'bool delete_guildhall(', 'bool delete_guildhall_room('):
    body = mariadb_branch(extract_function('guildhall_db.c', signature))
    if 'sql_queue(' not in body or 'qry(' in body:
        failures.append(f'{signature} does not queue its write on the writer')

for signature in ('int next_guildhall_id(', 'int next_guildhall_room_id('):
    body = extract_function('guildhall_db.c', signature)
    if 'qry(' in body or 'mysql_' in body:
        failures.append(f'{signature} still queries')

boot = mariadb_branch(extract_function('guildhall_db.c', 'void load_guildhalls('))
if 'max(id), 0) from guildhall_rooms' not in boot or '_next_guildhall_room_id =' not in boot:
    failures.append('the boot load does not read the highest stored ids')

reload = extract_function('guildhall.c', 'bool Guildhall::reload(')
if 'load_guildhall' in reload or 'make_guildhall_room(old_room->type)' not in reload:
    failures.append('Guildhall::reload() does not rebuild its rooms from memory')

for failure in failures:
    print(failure)
if not failures:
    print('guildhall writes are queued and reloads come from memory')
sys.exit(1 if failures else 0)
