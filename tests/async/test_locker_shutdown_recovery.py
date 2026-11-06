#!/usr/bin/env python3
"""Refuse live locker preparation, exit, and replay against isolated native SQL.

Never reads .env or connects to an existing server. Faults are controlled at the
gameplay/durability boundary; item capture, file publication, restart replay and
ownership writes execute production code in separate processes.
"""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import time
from _paths import ROOT, extract_function

build = ROOT / 'bin/tests/locker-shutdown-recovery'
build.mkdir(parents=True, exist_ok=True)
signatures = (
    'inline StorageLocker *GetChestList(',
    'StorageLocker::StorageLocker(',
    'LockerChest *StorageLocker::AddLockerChest(',
    'LockerChest *StorageLocker::FindChestForObject(',
    'std::vector<PrivateChest *> StorageLocker::GetPrivateChests(',
    'bool StorageLocker::ChestObjectsPresent(',
    'static StorageLocker *active_locker_for(',
    'static bool locker_recovery_append(',
    'bool locker_shutdown_capture(',
    'static std::vector<P_obj> locker_snapshot_room_contents(',
    'bool StorageLocker::LockerToPFile(',
    'static bool locker_handle_leave(',
)
bodies = '\n'.join(extract_function('item/storage_lockers.c', signature)
                   for signature in signatures)
bodies += '\n' + extract_function('net/comm.c', 'static void critical_gameplay_handle_completions(')
comm = (ROOT / 'src/net/comm.c').read_text()
publication_start = comm.index('critical_completion shutdown_completions[64];')
publication = comm[publication_start:comm.index('locker_recovery_begin();', publication_start)]
bodies = bodies.replace('bool StorageLocker::LockerToPFile(void)\n{',
                        'bool StorageLocker::LockerToPFile(void)\n{\n++prepare_calls;')
cpp = build / 'harness.cpp'
cpp.write_text((ROOT / 'tests/async/locker_shutdown_recovery_harness.cpp').read_text()
               .replace('// PRODUCTION_BODIES', bodies)
               .replace('// FINAL_COMPLETION_PUBLICATION', publication))
sources = [
    'src/persistence/locker_recovery.c', 'src/flatfile/flatfile_store.c',
    'src/persistence/locker_async.c',
    'src/item/item_movement_transaction.c', 'src/item/item_transfer_repository.c',
    'src/player/player_snapshot_capture.c', 'src/player/player_snapshot_codec.c',
    'src/player/player_snapshot_repository.c', 'src/item/item_claim_repository.c',
    'src/item/item_claim.c', 'src/persistence/dupe_log.c',
    'src/sql/item_extra_descr_codec.c', 'src/persistence/persistence_observability.c',
    'src/player/pet_restore_state.c', 'src/player/pet_restore_runtime.c',
    'src/item/item_ownership_runtime.c', 'src/item/item_transfer_command.c',
    'src/persistence/critical_command.c', 'tests/async/harness_stubs.cpp',
]
binary = build / 'harness'
subprocess.run(['g++', '-std=c++20', '-g', '-O1', '-Wall', '-Wextra', '-Werror',
                '-Wno-unused-parameter', '-pthread', '-ffunction-sections', '-fdata-sections',
                '-Isrc', *shlex.split(subprocess.check_output(['mysql_config', '--cflags'], text=True)),
                str(cpp), *sources, '-Wl,--gc-sections', '-Wl,--wrap=fsync',
                *shlex.split(subprocess.check_output(['mysql_config', '--libs'], text=True)),
                '-lcrypto', '-o', str(binary)], cwd=ROOT, check=True)

with tempfile.TemporaryDirectory(prefix='duris-locker-shutdown-') as td:
    work = Path(td)
    socket = str(work / 'mysql.sock')
    with (work / 'setup.log').open('w') as log:
        subprocess.run(['mariadb-install-db', '--no-defaults', f'--datadir={work}/data',
                        '--auth-root-authentication-method=normal', '--skip-test-db'],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    with (work / 'daemon.log').open('w') as log:
        server = subprocess.Popen(['mariadbd', '--no-defaults', f'--datadir={work}/data',
                                   f'--socket={socket}', '--skip-networking',
                                   f'--pid-file={work}/pid', f'--log-error={work}/server.log',
                                   '--innodb-buffer-pool-size=64M'], stdout=log, stderr=log)
        mysql = ['mysql', '--no-defaults', '--protocol=socket', f'--socket={socket}', '-uroot', '-N', '-B']
        try:
            for _ in range(100):
                assert server.poll() is None, (work / 'server.log').read_text()
                if subprocess.run(mysql + ['-e', 'SELECT 1'], capture_output=True).returncode == 0:
                    break
                time.sleep(.1)
            else:
                raise RuntimeError('isolated MariaDB did not start')

            def sql(statement, database='locker_recovery'):
                return subprocess.check_output(mysql + ([database] if database else []),
                                               input=statement, text=True).strip()

            sql("ALTER USER 'root'@'localhost' IDENTIFIED BY 'locker-test'", None)
            mysql.append('--password=locker-test')
            sql('CREATE DATABASE locker_recovery', None)
            sql((ROOT / 'migrations/bootstrap_multithread_safe.sql').read_text())
            sql((ROOT / 'migrations/immutable/0049_divine_boon_delivery.sql').read_text())
            sql((ROOT / 'migrations/immutable/0002_player_item_metadata_uniqueness.sql').read_text())
            sql((ROOT / 'migrations/immutable/0059_item_affect_slots.sql').read_text())
            sql((ROOT / 'migrations/immutable/0060_item_instance_fields.sql').read_text())

            def reset():
                sql('SET FOREIGN_KEY_CHECKS=0;' + ''.join('TRUNCATE TABLE ' + table + ';' for table in (
                    'player_items', 'locker_items', 'player_item_affects', 'player_item_extra_descr',
                    'locker_item_affects', 'locker_item_extra_descr', 'item_current_owner',
                    'item_owner_revision', 'item_owner_audit', 'item_ownership_ledger',
                    'critical_operation_inbox', 'private_chests', 'lockers', 'player_data')) +
                    'SET FOREIGN_KEY_CHECKS=1;'
                    "INSERT INTO player_data(pid,name,copper) VALUES(42,'Fixture',123);"
                    "INSERT INTO lockers(id,locker_name,owner_pid,racewar,race) VALUES(1,'Fixture.locker',42,0,0);"
                    "INSERT INTO private_chests(id,locker_id,chest_name,is_public) VALUES(2,1,'public',1),(3,1,'private',0);"
                    'INSERT INTO locker_items(locker_id,chest_id,vnum,obj_uid) VALUES(1,3,48,300);'
                    'INSERT INTO player_items(pid,vnum,obj_uid) VALUES(42,48,105);'
                    'INSERT INTO item_current_owner(item_uid,root_item_uid,owner_type,owner_id,owner_context_id,item_revision,vnum,state) '
                    'VALUES(300,300,5,1,3,1,48,1),(105,105,1,42,0,1,48,1);')

            def run(state, mode):
                result = subprocess.run([str(binary), socket, 'locker_recovery', str(state), mode],
                                        capture_output=True, text=True, timeout=10)
                assert result.returncode == 0, (mode, result.returncode, result.stdout, result.stderr)
                return result

            terminal_cases = ('queue', 'writer-failure', 'capture')
            for case in ('late-grant', 'write', 'purchase', 'durability', 'audit', 'prepare', *terminal_cases, 'reaped'):
                reset()
                state = work / case
                state.mkdir()
                if case == 'writer-failure':
                    sql("CREATE TRIGGER fail_write BEFORE INSERT ON locker_items FOR EACH ROW "
                        "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='synthetic writer failure'")
                shutdown = run(state, case)
                if case == 'writer-failure':
                    sql('DROP TRIGGER fail_write')
                assert 'RECOVERABLE locker shutdown:' in shutdown.stderr, shutdown.stderr
                image = state / 'runtime/locker-shutdown/shutdown.image'
                assert image.exists()
                saved = image.read_bytes()
                # First restart is stopped after public replacement by a synthetic
                # private write failure. The image must survive and replay safely.
                if case == 'prepare':
                    sql("DELIMITER //\nCREATE TRIGGER refuse_private BEFORE INSERT ON locker_items FOR EACH ROW "
                        "BEGIN IF NEW.chest_id=3 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='synthetic'; END IF; END//\nDELIMITER ;\n")
                    run(state, 'refuse-boot')
                    assert image.read_bytes() == saved
                    sql('DROP TRIGGER refuse_private')
                run(state, 'recover')
                assert not image.exists()
                public = sql('SELECT GROUP_CONCAT(obj_uid ORDER BY obj_uid) FROM locker_items WHERE chest_id=2')
                assert public == '100,101,102,104,105', public
                if case not in terminal_cases:
                    assert sql('SELECT GROUP_CONCAT(obj_uid ORDER BY obj_uid) FROM locker_items WHERE chest_id=3') == '200,201'
                expected_player = '300,301,400,401' if case == 'late-grant' else '300,301'
                assert sql('SELECT GROUP_CONCAT(obj_uid ORDER BY obj_uid) FROM player_items') == expected_player
                assert sql('SELECT value0 FROM locker_items WHERE obj_uid=102') == '37'
                assert sql('SELECT p.obj_uid FROM locker_items c JOIN locker_items p ON p.id=c.container_id WHERE c.obj_uid=101') == '100'
                assert sql('SELECT equip_slot FROM player_items WHERE obj_uid=301') == str(7)  # WEAR_HEAD + 1
                assert sql('SELECT copper FROM player_data WHERE pid=42') == '123'
                assert sql("SELECT CONCAT(owner_type,':',owner_id,':',owner_context_id) FROM item_current_owner WHERE item_uid=300") == '1:42:0'
                assert sql("SELECT CONCAT(owner_type,':',owner_id,':',owner_context_id) FROM item_current_owner WHERE item_uid=105") == '5:1:2'
                rows = sql('SELECT COUNT(*),COUNT(DISTINCT obj_uid) FROM (SELECT obj_uid FROM locker_items UNION ALL SELECT obj_uid FROM player_items) all_items')
                expected_count = 11 if case == 'late-grant' else 9 if case not in terminal_cases else 7
                # Terminal cases retain the old private payload copy of uid 300,
                # but its owner is the player; loaders omit that stale copy.
                assert rows == (f'{expected_count + 1}\t{expected_count}' if case in terminal_cases else f'{expected_count}\t{expected_count}'), rows
                visible = sql('SELECT COUNT(*),COUNT(DISTINCT uid) FROM ('
                              'SELECT li.obj_uid uid FROM locker_items li JOIN item_current_owner co '
                              'ON co.item_uid=li.obj_uid AND co.owner_type=5 AND co.owner_id=li.locker_id '
                              'AND co.owner_context_id=li.chest_id UNION ALL '
                              'SELECT pi.obj_uid uid FROM player_items pi JOIN item_current_owner co '
                              'ON co.item_uid=pi.obj_uid AND co.owner_type=1 AND co.owner_id=pi.pid) loaded_items')
                assert visible == f'{expected_count}\t{expected_count}', visible
                run(state, 'recover')  # second boot cannot repeat or duplicate recovery
                print(f'[PASS] {case}: process exit/restart, topology, quantities, ownership and item-only player recovery', flush=True)

            external_pending = ('shop-pending', 'auction-pending', 'collector-pending', 'quest-pending', 'other-fenced')
            for case in ('movement', 'ambiguous-grant', 'holder-missing', 'public-object-missing', 'malformed', 'blocked-publish', 'blocked-io', *external_pending,
                         'room-cycle', 'public-cycle', 'holder-cycle', 'occupant-cycle'):
                reset()
                state = work / case
                state.mkdir()
                started = time.monotonic()
                result = run(state, case)
                if case == 'blocked-io':
                    assert time.monotonic() - started < .75
                assert 'UNRECOVERED locker shutdown:' in result.stderr, result.stderr
                run(state, 'refuse-boot')
                assert sql('SELECT GROUP_CONCAT(obj_uid) FROM locker_items') == '300'
                if case == 'ambiguous-grant':
                    assert sql('SELECT GROUP_CONCAT(obj_uid ORDER BY obj_uid) FROM player_items') == '105,400,401'
                    assert sql('SELECT COUNT(*) FROM item_current_owner WHERE item_uid IN (400,401) AND owner_type=1 AND owner_id=42') == '2'
                if case in external_pending:
                    assert sql('SELECT GROUP_CONCAT(obj_uid ORDER BY obj_uid) FROM player_items') == '105,400'
                print(f'[PASS] {case}: explicit failure, retained evidence, restart refuses unsafe replacement', flush=True)

            for case in ('checksum', 'wrong-store'):
                reset()
                state = work / case
                state.mkdir()
                run(state, 'write')
                image = state / 'runtime/locker-shutdown/shutdown.image'
                if case == 'checksum':
                    damaged = bytearray(image.read_bytes())
                    damaged[len(damaged) // 2] ^= 1
                    image.write_bytes(damaged)
                    run(state, 'refuse-boot')
                else:
                    result = subprocess.run([str(binary), socket, 'locker_recovery', str(state), 'refuse-boot'],
                                            env=dict(os.environ, DB_HOST='another-store'),
                                            capture_output=True, text=True, timeout=10)
                    assert result.returncode == 0, result.stderr
                assert image.exists()
                assert sql('SELECT GROUP_CONCAT(obj_uid) FROM locker_items') == '300'
                print(f'[PASS] {case}: restart preserves evidence without applying it', flush=True)
        finally:
            server.terminate()
            server.wait(timeout=30)
