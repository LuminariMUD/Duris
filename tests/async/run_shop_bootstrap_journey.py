#!/usr/bin/env python3
"""Boot a fresh full-world MariaDB shop authority, then cold-restart it.

Uses the supplied server and the existing disposable world helpers. No checkout
.env or running game is used. Shop identities, stock and custody must survive
restoration; SQL rewrites may advance revisions and replace surrogate row IDs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority
from run_world_quest_dual_backend import setup_run_root

ROOT = journey.ROOT


def run(binary, output, areas=None):
    evidence = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'passed': False, 'boots': []}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='shop-bootstrap-') as temporary:
        runtime = Path(temporary)
        _, critical, log = setup_run_root(runtime)
        if areas is not None:
            assert (runtime / 'areas').is_symlink()
            (runtime / 'areas').unlink()
            (runtime / 'areas').symlink_to(areas, target_is_directory=True)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        plain, tls, websocket = journey.available_ports()
        with authority('mariadb', runtime) as (environment, sql):
            environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                               DURIS_WEBSOCKET_PORT=str(websocket))

            def catalog():
                stock = {'shopkeepers': sql('SELECT shop_id,mob_vnum,room_vnum FROM shopkeepers ORDER BY shop_id')}
                # Compare all payload columns using durable shop/item identities.
                # The writer replaces SQL rows on restore, so row IDs and write
                # timestamps are not stock identities or content.
                for table, joins, identity, excluded in (
                        ('shopkeeper_items', 'JOIN shopkeepers s ON s.id=i.shopkeeper_id '
                         'LEFT JOIN shopkeeper_items p ON p.id=i.container_id',
                         's.shop_id,COALESCE(p.obj_uid,0)', {'id', 'shopkeeper_id', 'container_id', 'created_at'}),
                        ('shopkeeper_item_affects', 'JOIN shopkeeper_items p ON p.id=i.item_id',
                         'p.obj_uid', {'id', 'item_id'}),
                        ('shopkeeper_item_extra_descr', 'JOIN shopkeeper_items p ON p.id=i.item_id',
                         'p.obj_uid', {'id', 'item_id'})):
                    columns = sql("SELECT column_name FROM information_schema.columns WHERE table_schema=DATABASE() "
                                  "AND table_name='" + table + "' ORDER BY ordinal_position").splitlines()
                    payload = ','.join('i.`' + column + '`' for column in columns if column not in excluded)
                    assert payload, table
                    stock[table] = sorted(sql('SELECT ' + identity + ',' + payload + ' FROM ' + table + ' i ' + joins).splitlines())
                stock['custody'] = sql('SELECT item_uid,root_item_uid,COALESCE(parent_item_uid,0),owner_id,'
                                       'owner_context_id,vnum,state FROM item_current_owner WHERE owner_type=9 ORDER BY item_uid')
                revisions = dict(tuple(map(int, row.split('\t'))) for row in sql(
                    'SELECT owner_id,revision FROM item_owner_revision WHERE owner_type=9').splitlines())
                # NPCs can cast buffs (e.g. biofeedback) during the first game
                # pulse. Their live affects are not immutable shop stock.
                assert stock['shopkeepers'] and stock['shopkeeper_items'] and revisions, 'fresh shops have no persisted stock'
                return stock, revisions

            baseline, previous_revisions = None, None
            try:
                for iteration in range(2):
                    offset = log.stat().st_size if log.exists() else 0
                    with log.open('a') as stream:
                        process = subprocess.Popen([str(binary), '-d', str(runtime), str(plain)], cwd=runtime,
                                                   env=environment, stdout=stream, stderr=subprocess.STDOUT)
                    try:
                        deadline = time.monotonic() + 120
                        while 'Entering game loop.' not in log.read_text(errors='replace')[offset:]:
                            assert process.poll() is None and time.monotonic() < deadline, log.read_text(errors='replace')[-4000:]
                            time.sleep(.1)
                    finally:
                        if process.poll() is None:
                            process.terminate()
                            process.wait(timeout=45)
                        assert process.returncode == 0, 'full-world boot/shutdown failed'
                    stock, revisions = catalog()
                    digest = hashlib.sha256(json.dumps(stock, sort_keys=True).encode()).hexdigest()
                    evidence['boots'].append({'iteration': iteration, 'catalog_sha256': digest,
                                              'shops': len(stock['shopkeepers'].splitlines()),
                                              'items': len(stock['shopkeeper_items']), 'revisions': revisions})
                    if baseline is not None:
                        changes = {}
                        for table in stock:
                            before = baseline[table].splitlines() if isinstance(baseline[table], str) else baseline[table]
                            after = stock[table].splitlines() if isinstance(stock[table], str) else stock[table]
                            if before != after:
                                changes[table] = {'removed': sorted(set(before) - set(after))[:5],
                                                  'added': sorted(set(after) - set(before))[:5]}
                        evidence['changes'] = changes
                        assert stock == baseline, ('restart changed existing stock identities, contents or custody', changes)
                        assert revisions.keys() == previous_revisions.keys()
                        assert all(revisions[owner] >= revision for owner, revision in previous_revisions.items()), 'restart regressed a shop revision'
                    baseline, previous_revisions = stock, revisions
                    print('[PASS] full-world shop', 'initialization' if iteration == 0 else 'cold restoration', flush=True)
                evidence['passed'] = True
            finally:
                output.write_text(json.dumps(evidence, indent=2))
                if log.exists():
                    output.with_suffix('.log').write_bytes(log.read_bytes())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, required=True)
    parser.add_argument('--areas', type=Path, help='isolated generated full-world area directory')
    parser.add_argument('--output', type=Path, default=ROOT / 'bin/qualification/shop-bootstrap.json')
    args = parser.parse_args()
    run(args.server.resolve(), args.output.resolve(), args.areas.resolve() if args.areas else None)
