#!/usr/bin/env python3
"""Misty Vale shop repair; database cases run in run_migration_runner_engines.py."""
from pathlib import Path
import re
import sys
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import migration_runner as runner


def catalogue():
    """Read the same AREA order and tilde-delimited records as make_shp/boot_the_shops."""
    shops = []
    for line in (ROOT / 'areas/AREA').read_text().splitlines():
        if not line.strip() or line.startswith('*'):
            continue
        path = ROOT / 'areas/shp' / (line.split()[0] + '.shp')
        if not path.exists():
            matches = [p for p in path.parent.iterdir() if p.name.lower() == path.name.lower()]
            if not matches:
                continue
            path = matches[0]
        for record in re.split(r'(?m)^#', path.read_text(encoding='latin1'))[1:]:
            fields = record.split('~')[8].split()
            shops.append((int(fields[2]), 0 if fields[9] == 'Y' else int(fields[4])))
    assert shops[534] == (300036, 300056)
    return shops


def check_catalogue():
    shops = catalogue()
    step = runner.load_manifest().migrations[-1]
    assert step.migration_id == '0053_misty_vale_shop_indexes'
    actual = [tuple(map(int, row)) for row in re.findall(
        r'\((\d+),(\d+),(\d+)\)', step.apply_path.read_text())]
    assert actual == [(i, *identity) for i, identity in enumerate(shops) if i > 534], (
        'migration must cover every shop shifted by the insertion, including end.shp')
    return actual


def check_shop_reindex(sql, migrate, environment):
    """Exercise real SQL, verifier, rollback and success-last history on each engine."""
    mapping = check_catalogue()
    manifest = runner.load_manifest()
    step = manifest.migrations[-1]
    tables = ('shopkeepers', 'shopkeeper_items', 'shopkeeper_affects',
              'shopkeeper_item_affects', 'shopkeeper_item_extra_descr',
              'item_current_owner', 'item_owner_revision', 'item_ownership_baseline',
              'item_owner_audit', 'item_ownership_ledger')

    def snapshot():
        return {table: sql(f'SELECT * FROM {table} ORDER BY 1,2') for table in tables}

    def clear():
        # Only fixtures in the disposable runner_engines database are touched.
        sql('DELETE FROM shopkeepers')
        sql('DELETE FROM item_current_owner WHERE item_uid BETWEEN 8000 AND 9000')
        sql('DELETE FROM item_owner_revision WHERE owner_id BETWEEN 534 AND 554')

    def seed(indices=None, repaired=()):
        indices = set(range(len(mapping))) if indices is None else set(indices)
        for n, (new, mob, room) in enumerate(mapping):
            if n not in indices:
                continue
            old = new if n in repaired else new - 1
            room = room or 402150  # Roaming keepers need not be in the local snapshot's room.
            sql(f"INSERT INTO shopkeepers(id,shop_id,mob_vnum,room_vnum,save_time,updated_at) "
                f"VALUES({9000+n},{old},{mob},{room},'2026-10-01','2026-10-02')")
            sql(f"INSERT INTO shopkeeper_items(id,shopkeeper_id,vnum,obj_uid,equip_slot,cost) "
                f"VALUES({8000+n},{9000+n},42,{8000+n},{n % 4},123)")
            sql(f"INSERT INTO item_current_owner(item_uid,root_item_uid,owner_type,owner_id,"
                f"item_revision,vnum,updated_at) VALUES({8000+n},{8000+n},9,{old+1},7,42,'2026-10-02')")
            sql(f"INSERT INTO item_owner_revision(owner_type,owner_id,revision,updated_at) "
                f"VALUES(9,{old+1},13,'2026-10-02')")
        if 0 in indices:
            sql('INSERT INTO shopkeeper_items(id,shopkeeper_id,vnum,obj_uid,container_id) '
                'VALUES(8999,9000,43,8999,8000)')
            sql('INSERT INTO shopkeeper_affects(shopkeeper_id,type,duration) VALUES(9000,17,23)')
            sql('INSERT INTO shopkeeper_item_affects(item_id,location,modifier) VALUES(8999,3,7)')
            sql("INSERT INTO shopkeeper_item_extra_descr(item_id,keyword,description) "
                "VALUES(8999,'test','preserve nested stock')")

    # The real runner must not publish success for an incompatible catalogue.
    sql('INSERT INTO shopkeepers(shop_id,mob_vnum,room_vnum) VALUES(534,42,43)')
    before = snapshot()
    failed = migrate('run')
    assert failed.returncode == 2 and 'shop catalogue conflicts' in failed.stderr, failed.stderr
    assert snapshot() == before
    assert sql('SELECT applied_count FROM mud_schema_migration_state') == str(step.sequence - 1)
    clear()

    # Historical observations keep the indexes they recorded. Live custody moves.
    sql("INSERT INTO item_ownership_baseline(item_uid,root_item_uid,owner_type,owner_id,"
        "source_table,source_row_id) VALUES(8990,8990,9,535,'shopkeeper_items',8990)")
    sql('INSERT INTO item_owner_audit(item_uid,vnum,old_owner_type,old_owner_id,old_owner_context_id,'
        'new_owner_type,new_owner_id,new_owner_context_id) VALUES(8990,42,1,7,0,9,535,0)')
    sql("INSERT INTO critical_operation_inbox(operation_id,command_hash,keys_hash,command_type,"
        "schema_version,payload_version,status,result_payload) "
        "VALUES(UNHEX(REPEAT('61',16)),UNHEX(REPEAT('cd',32)),UNHEX(REPEAT('ef',32)),5,1,1,1,'')")
    sql("INSERT INTO item_ownership_ledger(operation_id,event_index,item_uid,root_item_uid,"
        "from_owner_type,from_owner_id,from_owner_context_id,to_owner_type,to_owner_id,"
        "to_owner_context_id,item_revision,from_owner_revision,to_owner_revision,reason_type,source_site) "
        "VALUES(UNHEX(REPEAT('61',16)),0,8990,8990,1,7,0,9,535,0,1,1,1,1,1)")

    with mock.patch.dict('os.environ', environment):
        executor = runner.MysqlExecutor(manifest)
        executor.acquire_lock()
        try:
            def rejected(message):
                before = snapshot()
                try:
                    executor.apply(step)
                except runner.MigrationContractError as error:
                    assert message in str(error), str(error)
                    executor.release_lock()
                    executor.acquire_lock()
                else:
                    raise AssertionError('conflicting repair was accepted')
                assert snapshot() == before, 'failed repair changed saved data'

            # Empty database, full old catalogue, already repaired, mixed, sparse.
            for indices, repaired in (([], []), (None, []), (None, range(18)),
                                      (None, range(8,18)), ([0,2,6,17], [])):
                clear()
                seed(indices, repaired)
                before = snapshot()
                expected = sql('SELECT id,mob_vnum,room_vnum,save_time,updated_at FROM shopkeepers ORDER BY id')
                executor.apply(step)
                executor.verify(step)
                after = snapshot()
                assert sql('SELECT id,mob_vnum,room_vnum,save_time,updated_at FROM shopkeepers ORDER BY id') == expected
                for table in set(tables) - {'shopkeepers','item_current_owner','item_owner_revision'}:
                    assert after[table] == before[table], table
                for n, (new, _, _) in enumerate(mapping):
                    if indices is not None and n not in indices:
                        continue
                    assert sql(f'SELECT shop_id FROM shopkeepers WHERE id={9000+n}') == str(new)
                    assert sql(f'SELECT owner_id,item_revision,updated_at FROM item_current_owner '
                               f'WHERE item_uid={8000+n}') == f'{new+1}\t7\t2026-10-02 00:00:00.000000'
                    assert sql(f'SELECT revision,updated_at FROM item_owner_revision WHERE '
                               f'owner_type=9 AND owner_id={new+1}') == '13\t2026-10-02 00:00:00.000000'
                executor.apply(step)  # crash after COMMIT but before history publication
                executor.verify(step)
                assert snapshot() == after, 'replay changed saved data'

            # An installed new shop and unrelated owners sharing numeric IDs survive.
            clear()
            seed(repaired=range(18))
            sql('INSERT INTO shopkeepers(id,shop_id,mob_vnum,room_vnum) VALUES(9100,534,300036,300056)')
            sql('INSERT INTO item_owner_revision(owner_type,owner_id,revision) VALUES(1,535,29)')
            before = snapshot()
            executor.apply(step)
            executor.verify(step)
            assert snapshot() == before

            for mutation in (
                'UPDATE shopkeepers SET room_vnum=1 WHERE id=9000',
                'UPDATE shopkeepers SET mob_vnum=NULL WHERE id=9000',
                'UPDATE shopkeepers SET room_vnum=NULL WHERE id=9001',
                'UPDATE shopkeepers SET shop_id=553 WHERE id=9000',
            ):
                clear()
                seed()
                sql(mutation)
                rejected('shop catalogue conflicts')
            clear()
            seed(indices=[0])
            sql('INSERT INTO shopkeepers(shop_id,mob_vnum,room_vnum) VALUES(535,400004,400000)')
            rejected('shop identity is duplicated')

            # The last destination is free, so the error happens after earlier updates.
            # The entire transaction, including current custody, must still roll back.
            for table in ('item_current_owner', 'item_owner_revision'):
                clear()
                seed(indices=[0,17])
                if table == 'item_current_owner':
                    sql('INSERT INTO item_current_owner(item_uid,root_item_uid,owner_type,owner_id) '
                        'VALUES(8998,8998,9,536)')
                else:
                    sql('INSERT INTO item_owner_revision(owner_type,owner_id,revision) VALUES(9,536,23)')
                rejected('shop destination is occupied')

            clear()
            seed()
            sql("DELIMITER //\nCREATE TRIGGER fail_shop_reindex BEFORE UPDATE ON shopkeepers FOR EACH ROW "
                "BEGIN IF OLD.id=9000 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='injected failure'; END IF; END//\nDELIMITER ;")
            rejected('injected failure')
            sql('DROP TRIGGER fail_shop_reindex')
            executor.apply(step)
            executor.verify(step)
            sql('UPDATE shopkeepers SET room_vnum=1 WHERE id=9000')
            before = snapshot()
            try:
                executor.verify(step)
            except runner.MigrationContractError:
                pass
            else:
                raise AssertionError('verifier accepted wrong keeper room')
            assert snapshot() == before
            clear()
            sql('ALTER TABLE item_owner_revision ENGINE=MyISAM')
            rejected('requires InnoDB')
            sql('ALTER TABLE item_owner_revision ENGINE=InnoDB')
            assert sql('SELECT applied_count FROM mud_schema_migration_state') == str(step.sequence - 1)
        finally:
            executor.release_lock()

    # Leave actual old records for the caller's successful run/history/replay checks.
    seed()


if __name__ == '__main__':
    check_catalogue()
    print('Misty Vale migration matches all 18 shifted AREA shop identities')
