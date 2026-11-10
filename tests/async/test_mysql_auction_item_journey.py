#!/usr/bin/env python3
"""Auction source/target refusal, disconnect, legacy conversion and exact UID restart."""
import argparse
from pathlib import Path
import tempfile
import time

import test_mariadb_combat_journey as journey
from run_item_pilot_journey import Server
from run_world_quest_dual_backend import collect_logs
from test_flight_network_journey import authority, command

ROOT = journey.ROOT
PLAYER, ACCOUNT = 'Itembuyer', 'Itemaccount'
UIDS = (980012, 980013)
EXPECTED = ['980012|53|98|a crimson sample bag', '980013|71|96|an azure sample bag']


def run(binary):
    (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='auction-items-', dir=ROOT / 'bin/tests') as temporary:
        runtime = Path(temporary)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        (runtime / 'logs/log').mkdir(parents=True)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        properties = runtime / 'lib/duris.properties'
        rates = properties.read_text()
        assert 'auctions.startPricePctFee=0.040' in rates
        properties.write_text(rates.replace('auctions.startPricePctFee=0.040',
                                           'auctions.startPricePctFee=0.020'))
        with authority('mariadb', runtime) as (env, sql):
            server = Server(binary, runtime, runtime, 'auction-items', environment=env)
            client = None

            def login():
                nonlocal client
                client = journey.reconnect_character(server.port, expected_room=None,
                                                     account=ACCOUNT, character=PLAYER)
                client.expect('Welcome to Duris', timeout=60)
                client.expect('Pos: standing >', timeout=20)
                command(client, 'toggle paging no')

            def stop(crash=False):
                nonlocal client
                if client:
                    client.close()
                    client = None
                if crash:
                    server.process.kill()
                    server.process.wait(timeout=10)
                server.stop()

            def wallet():
                return int(sql('SELECT copper+10*silver+100*gold+1000*platinum '
                               f"FROM player_data WHERE name='{PLAYER}'"))

            def graph():
                return sql("SELECT CONCAT(obj_uid,'|',value0,'|',item_condition,'|',short_descr) "
                           f'FROM player_items WHERE pid={pid} AND obj_uid BETWEEN 980012 AND 980014 '
                           'ORDER BY obj_uid').splitlines()

            def await_graph(expected):
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    actual = graph()
                    if actual == expected:
                        return
                    time.sleep(.05)
                raise AssertionError(('auction inventory did not settle', expected, actual))

            try:
                server.start(full_world=True)
                client = journey.MudClient(server.port)
                journey.create_character(client, expected_room=None, account=ACCOUNT,
                                         character=PLAYER, email='itembuyer@example.invalid')
                command(client, 'save')
                stop()
                pid = int(sql(f"SELECT pid FROM player_data WHERE name='{PLAYER}'"))
                sql(f'DELETE FROM player_items WHERE pid={pid};'
                    'INSERT INTO player_items(pid,vnum,obj_uid,name,short_descr,item_type,weight,'
                    'item_condition,value0,value3) VALUES '
                    f"({pid},391,980012,'saleitem crimson bag','a crimson sample bag',15,1,98,53,100),"
                    f"({pid},391,980013,'saleitem azure bag','an azure sample bag',15,1,96,71,100);"
                    'INSERT INTO item_current_owner(item_uid,root_item_uid,owner_type,owner_id,'
                    'owner_context_id,item_revision,vnum,state) VALUES '
                    f'(980012,980012,1,{pid},0,1,391,1),(980013,980013,1,{pid},0,1,391,1);'
                    f'UPDATE player_data SET platinum=10,gold=0,silver=0,copper=0,wallet_revision=0,'
                    f'last_room=16885 WHERE pid={pid}')
                server.start(full_world=True)
                login()
                assert graph() == EXPECTED
                response = command(client, 'auction offer saleitem 1 0 1 2')
                assert 'is now listed as auction' in response, response
                auction_id = int(sql(f'SELECT auction_id FROM auction_item_custody WHERE item_uid={UIDS[0]}'))
                command(client, 'save')
                await_graph([])
                assert wallet() == 8980
                stop()

                # Stage the same seller's returned lot as an expired auction.
                sql(f'UPDATE auctions SET status=2 WHERE id={auction_id};'
                    f'UPDATE auction_item_custody SET claim_pid={pid} WHERE auction_id={auction_id}')
                server.start(full_world=True)
                login()
                sql('DELIMITER //\nCREATE TRIGGER reject_claim_item BEFORE INSERT ON player_items FOR EACH ROW '
                    f'BEGIN IF NEW.pid={pid} AND NEW.obj_uid IN (980012,980013) THEN '
                    "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='auction target refusal'; END IF; END//\nDELIMITER ;\n")
                client.send('auction pickup')
                client.expect('items remain available', timeout=30)
                assert graph() == [] and wallet() == 8980
                assert sql(f'SELECT COUNT(*) FROM auction_item_custody WHERE auction_id={auction_id} '
                           'AND claimed_at IS NULL') == '2'
                assert sql('SELECT COUNT(*) FROM item_current_owner WHERE item_uid IN (980012,980013) '
                           f'AND owner_type=6 AND owner_id={auction_id} AND state=1') == '2'
                stop(crash=True)
                sql('DROP TRIGGER reject_claim_item')
                server.start(full_world=True)
                login()
                assert graph() == [] and wallet() == 8980
                print('PASS refused claim + SIGKILL preserves both auction UIDs and purse', flush=True)

                # Drop the session after admission, before relying on its completion message.
                client.send('auction pickup')
                client.expect('being committed', timeout=20)
                client.close()
                client = None
                await_graph(EXPECTED)
                assert wallet() == 8980
                stop(crash=True)
                server.start(full_world=True)
                login()
                command(client, 'save')
                await_graph(EXPECTED)
                assert sql('SELECT COUNT(*) FROM item_current_owner WHERE item_uid IN (980012,980013) '
                           f'AND owner_type=1 AND owner_id={pid} AND state=1') == '2'
                client.send('auction pickup')
                client.expect('no items or money', timeout=30)
                command(client, 'save')
                assert graph() == EXPECTED and wallet() == 8980
                print('PASS lost acknowledgement/disconnect + restart owns both distinct snapshots exactly once', flush=True)

                # Old persisted listings contain the legacy display serialization.
                first_uid = int(sql('SELECT item_uid FROM auction_item_custody '
                                    f'WHERE auction_id={auction_id} ORDER BY slot LIMIT 1'))
                legacy_expected = '980014|' + next(row.split('|', 1)[1] for row in EXPECTED
                                                 if row.startswith(str(first_uid) + '|'))
                legacy_auction = int(sql('INSERT INTO auctions(seller_pid,seller_name,start_time,end_time,status,'
                    'cur_price,buy_price,obj_short,obj_vnum,obj_blob_str,quantity,auction_revision,custody_state) '
                    'SELECT seller_pid,seller_name,NOW(),NOW(),2,cur_price,0,obj_short,obj_vnum,obj_blob_str,1,1,1 '
                    f'FROM auctions WHERE id={auction_id}; SELECT LAST_INSERT_ID()'))
                sql('INSERT INTO item_owner_revision(owner_type,owner_id,owner_context_id,revision) '
                    f'VALUES(6,{legacy_auction},0,0);'
                    'INSERT INTO item_current_owner(item_uid,root_item_uid,owner_type,owner_id,'
                    'owner_context_id,item_revision,vnum,state) '
                    f'VALUES(980014,980014,6,{legacy_auction},0,1,391,1);'
                    'INSERT INTO auction_item_custody(auction_id,slot,item_uid,item_revision,vnum,obj_blob,claim_pid) '
                    f'SELECT {legacy_auction},0,980014,1,391,obj_blob_str,{pid} FROM auctions WHERE id={auction_id}')
                client.send('auction pickup')
                client.expect('You pick up', timeout=30)
                expected_all = EXPECTED + [legacy_expected]
                await_graph(expected_all)
                command(client, 'save')
                stop(crash=True)
                server.start(full_world=True)
                login()
                command(client, 'save')
                await_graph(expected_all)
                assert wallet() == 8980
                print('PASS legacy listing converts on public pickup; exact UID/attributes survive restart', flush=True)
            except Exception:
                target = ROOT / 'bin/tests/auction-item-failure.log'
                target.write_text(collect_logs(runtime) + '\n' +
                                  server.output_path.read_text(errors='replace') + '\n' +
                                  (bytes(client.transcript).decode(errors='replace') if client else ''))
                print('Failure evidence: ' + str(target), flush=True)
                raise
            finally:
                stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', type=Path, default=ROOT / 'bin/server/dms_new')
    run(parser.parse_args().server.resolve())
